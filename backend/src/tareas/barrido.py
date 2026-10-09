"""Barrido de vencimientos y de conciliacion.

Corre dentro del proceso de la API porque usa la misma instancia de pasarela
que ella: la falsa guarda su estado por proceso. Nunca llama a la pasarela
directo, todo pasa por `src.services.contratacion` y `src.services.webhooks`.

Ademas de vencer, reintenta los webhooks que fallaron y concilia los intentos
que esperan el 3DS hace mas de `abandono_3ds`, llegue o no un webhook: ONVO no
avisa cuando se aprueba una autorizacion.

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
from src.services import contratacion, pedidos, webhooks
from src.services.contratacion import ResultadoConciliacion

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
    eventos_pendientes: Conteo = Conteo()
    intentos_en_espera: Conteo = Conteo()

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
            logger.error(  # noqa: TRY400  sin traza: puede traer datos de la pasarela
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
        logger.error(  # noqa: TRY400  sin traza: puede traer datos de la pasarela
            "Barrido: fallo completar_vencidos (%s)", type(exc).__name__
        )
        return Conteo(fallidos=1)
    return Conteo(hechos=completados)


async def _procesar_eventos(
    sesiones: Sesiones,
    pasarela: PasarelaDePagos,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> Conteo:
    """Cada webhook pendiente en su transaccion. Si falla, el intento se anota
    en otra."""
    async with sesiones() as session:
        ids = await webhooks.pendientes(session, ahora=ahora)
    hechos = fallidos = 0
    for evento_id in ids:
        try:
            async with sesiones.begin() as session:
                hecho = await webhooks.procesar(
                    session, pasarela, evento_id, ahora=ahora, politicas=politicas
                )
        except Exception as exc:  # noqa: BLE001  un evento no frena a los demas
            fallidos += 1
            logger.error(  # noqa: TRY400  sin traza: puede traer datos de la pasarela
                "Barrido de webhooks: fallo el evento %s (%s)",
                evento_id,
                type(exc).__name__,
            )
            try:
                async with sesiones.begin() as session:
                    await webhooks.registrar_fallo(
                        session, evento_id, type(exc).__name__
                    )
            except Exception as otra:  # noqa: BLE001  se reintenta en la proxima vuelta
                logger.error(  # noqa: TRY400  sin traza: puede traer datos de la pasarela
                    "Barrido de webhooks: no se anoto el fallo del evento %s (%s)",
                    evento_id,
                    type(otra).__name__,
                )
            continue
        hechos += hecho
    return Conteo(hechos, fallidos)


async def _conciliar_intentos(
    sesiones: Sesiones,
    pasarela: PasarelaDePagos,
    referencias: Iterable[str],
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> Conteo:
    """Cada intento en espera en su transaccion. Los logs no llevan la
    referencia de la pasarela."""
    hechos = fallidos = 0
    for referencia in referencias:
        try:
            async with sesiones.begin() as session:
                conciliacion = await contratacion.conciliar_cobro(
                    session, pasarela, referencia, ahora=ahora, politicas=politicas
                )
        except Exception as exc:  # noqa: BLE001  un intento no frena a los demas
            fallidos += 1
            logger.error(  # noqa: TRY400  sin traza: puede traer datos de la pasarela
                "Barrido de intentos en espera: fallo una conciliacion (%s)",
                type(exc).__name__,
            )
            continue
        if conciliacion.resultado is ResultadoConciliacion.REGISTRADO:
            hechos += 1
        elif conciliacion.resultado is ResultadoConciliacion.DISCREPANCIA:
            logger.error("Barrido de intentos en espera: %s", conciliacion.detalle)
    return Conteo(hechos, fallidos)


async def barrer(
    sesiones: Sesiones,
    pasarela: PasarelaDePagos,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> ResumenBarrido:
    # Primero los webhooks: lo que registran ya no es candidato a vencer
    eventos_pendientes = await _procesar_eventos(
        sesiones, pasarela, ahora=ahora, politicas=politicas
    )
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

    # Antes que los vencimientos: un pago que ya se hizo no se cancela
    intentos = await _conciliar_intentos(
        sesiones,
        pasarela,
        candidatos.intentos_en_espera,
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
        eventos_pendientes=eventos_pendientes,
        intentos_en_espera=intentos,
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
