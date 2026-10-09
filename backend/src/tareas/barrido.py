"""Barrido de vencimientos.

Corre dentro del proceso de la API porque usa la misma instancia de pasarela
que ella: la falsa guarda su estado por proceso. Nunca llama a la pasarela
directo, todo pasa por `src.services.contratacion`.

Cada pedido va en su propia sesion y transaccion: una falla se registra y no
frena a los demas. Dos procesos pueden barrer a la vez sin bloqueo global:
cada operacion bloquea perfil y pedido y vuelve a comprobar su condicion, asi
que el segundo no hace nada.
"""

import asyncio
import dataclasses
import logging
import uuid
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.politicas import PoliticasPedido
from src.payments.contrato import PasarelaDePagos
from src.services import contratacion, pedidos

logger = logging.getLogger(__name__)

Sesiones = async_sessionmaker[AsyncSession]
Operacion = Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class Conteo:
    hechos: int = 0
    fallidos: int = 0


@dataclass(frozen=True)
class ResumenBarrido:
    la_quiero_abandonados: Conteo
    autorizaciones_vencidas: Conteo
    reautorizaciones_vencidas: Conteo
    eventos_impagos: Conteo
    completados: Conteo

    @property
    def vacio(self) -> bool:
        return all(
            getattr(self, campo.name) == Conteo() for campo in dataclasses.fields(self)
        )


async def _aplicar(
    sesiones: Sesiones,
    pasarela: PasarelaDePagos,
    operacion: Operacion,
    ids: Iterable[uuid.UUID],
    *,
    caso: str,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> tuple[Conteo, list[uuid.UUID]]:
    """Un pedido por transaccion. Devuelve el conteo y los pedidos tocados."""
    hechos: list[uuid.UUID] = []
    fallidos = 0
    for pedido_id in ids:
        try:
            async with sesiones.begin() as session:
                hecho = await operacion(
                    session, pasarela, pedido_id, ahora=ahora, politicas=politicas
                )
        # Sin el mensaje: puede traer datos de la pasarela
        except Exception as exc:  # noqa: BLE001  un pedido no frena a los demas
            fallidos += 1
            logger.warning(
                "Barrido de %s: fallo el pedido %s (%s)",
                caso,
                pedido_id,
                type(exc).__name__,
            )
            continue
        if hecho:
            hechos.append(pedido_id)
    return Conteo(len(hechos), fallidos), hechos


async def _completar(sesiones: Sesiones, ahora: datetime) -> Conteo:
    try:
        async with sesiones.begin() as session:
            completados = await pedidos.completar_vencidos(session, ahora=ahora)
    except Exception as exc:  # noqa: BLE001  el barrido sigue en la proxima vuelta
        logger.warning("Barrido: fallo completar_vencidos (%s)", type(exc).__name__)
        return Conteo(fallidos=1)
    return Conteo(hechos=completados)


async def barrer(
    sesiones: Sesiones,
    pasarela: PasarelaDePagos,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> ResumenBarrido:
    async with sesiones() as session:
        candidatos = await pedidos.candidatos_vencimiento(
            session, ahora=ahora, politicas=politicas
        )

    async def aplicar(
        operacion: Operacion, ids: Iterable[uuid.UUID], caso: str
    ) -> tuple[Conteo, list[uuid.UUID]]:
        return await _aplicar(
            sesiones,
            pasarela,
            operacion,
            ids,
            caso=caso,
            ahora=ahora,
            politicas=politicas,
        )

    la_quiero, _ = await aplicar(
        contratacion.soltar_la_quiero_abandonado,
        candidatos.la_quiero_abandonados,
        "La quiero abandonados",
    )
    autorizaciones, vencidos = await aplicar(
        contratacion.vencer_autorizacion,
        candidatos.autorizaciones_vencidas,
        "autorizaciones vencidas",
    )
    # Un saldo que vencio en esta vuelta puede tener ya el plazo de
    # reautorizacion pasado. Si no lo tiene, la operacion no hace nada.
    reautorizaciones, _ = await aplicar(
        contratacion.cerrar_reautorizacion_vencida,
        dict.fromkeys((*candidatos.reautorizaciones_vencidas, *vencidos)),
        "reautorizaciones vencidas",
    )
    eventos, _ = await aplicar(
        contratacion.cancelar_evento_impago,
        candidatos.eventos_impagos,
        "eventos impagos",
    )
    return ResumenBarrido(
        la_quiero_abandonados=la_quiero,
        autorizaciones_vencidas=autorizaciones,
        reautorizaciones_vencidas=reautorizaciones,
        eventos_impagos=eventos,
        completados=await _completar(sesiones, ahora),
    )


async def ciclo(
    sesiones: Sesiones,
    pasarela: PasarelaDePagos,
    *,
    intervalo: float,
    politicas_de: Callable[[], PoliticasPedido],
    reloj: Callable[[], datetime],
) -> None:
    """Barre cada `intervalo` segundos, para siempre. Solo lo corta la
    cancelacion de la tarea."""
    while True:
        try:
            resumen = await barrer(
                sesiones, pasarela, ahora=reloj(), politicas=politicas_de()
            )
            if not resumen.vacio:
                logger.info("Barrido de vencimientos: %s", resumen)
        # Una vuelta fallida no corta el ciclo. CancelledError no es Exception
        except Exception:
            logger.exception("Fallo una vuelta del barrido de vencimientos")
        await asyncio.sleep(intervalo)
