"""Webhooks de la pasarela: se guardan una sola vez y se procesan conciliando.

Recibir verifica el origen con `parsear_webhook` y guarda el evento; la
restriccion unica (proveedor, evento_externo_id) hace que un evento repetido
no se guarde dos veces. Procesar es conciliar el cobro del evento con
`contratacion.conciliar_cobro`, que solo consulta la pasarela: lo que dice el
webhook no se cree.

Hace flush y nunca commit: confirma quien llama, la API o el barrido.
Bloqueos: el evento antes que perfil, pedido, consulta y obra.
"""

import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.politicas import PoliticasPedido
from src.models import EventoPasarela
from src.payments.contrato import PasarelaDePagos, TipoEvento
from src.services import contratacion
from src.services.contratacion import ResultadoConciliacion
from src.services.paginacion import ParametrosPagina, traer_pagina

INTENTOS_MAXIMOS_EVENTO = 5
ESPERA_REINTENTO_EVENTO = timedelta(minutes=1)
TOPE_PENDIENTES = 100

# Eventos sobre un cobro: se concilian si traen referencia
TIPOS_DE_COBRO = frozenset(
    {
        TipoEvento.COBRO_AUTORIZADO,
        TipoEvento.COBRO_CAPTURADO,
        TipoEvento.COBRO_FALLIDO,
        TipoEvento.AUTORIZACION_VENCIDA,
        TipoEvento.REEMBOLSO_CONFIRMADO,
    }
)
# Con estos el evento queda procesado y con el detalle para moderacion
_PARA_MODERACION = frozenset(
    {ResultadoConciliacion.DISCREPANCIA, ResultadoConciliacion.SIN_COBRO}
)


async def recibir(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    cuerpo: bytes,
    encabezados: Mapping[str, str],
) -> EventoPasarela:
    """Guarda el evento, o devuelve el que ya estaba. Las excepciones de
    `parsear_webhook` suben y no se guarda nada."""
    evento = await pasarela.parsear_webhook(cuerpo, encabezados)
    payload: dict[str, Any] = dict(evento.payload)
    insertar = (
        insert(EventoPasarela)
        .values(
            proveedor=evento.proveedor,
            evento_externo_id=evento.evento_externo_id,
            tipo=str(evento.tipo),
            referencia=evento.referencia,
            payload=payload,
        )
        .on_conflict_do_nothing(index_elements=["proveedor", "evento_externo_id"])
    )
    await session.execute(insertar)
    leido = (
        select(EventoPasarela)
        .where(
            EventoPasarela.proveedor == evento.proveedor,
            EventoPasarela.evento_externo_id == evento.evento_externo_id,
        )
        .execution_options(populate_existing=True)
    )
    return (await session.execute(leido)).scalar_one()


async def procesar(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    evento_id: uuid.UUID,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> bool:
    """Concilia el cobro del evento y lo marca procesado. False si otro lo
    esta procesando o ya estaba procesado."""
    stmt = (
        select(EventoPasarela)
        .where(EventoPasarela.id == evento_id)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )
    evento = (await session.execute(stmt)).scalar_one_or_none()
    if evento is None or evento.procesado_en is not None:
        return False

    detalle = None
    if evento.tipo in TIPOS_DE_COBRO and evento.referencia is not None:
        conciliacion = await contratacion.conciliar_cobro(
            session, pasarela, evento.referencia, ahora=ahora, politicas=politicas
        )
        if conciliacion.resultado in _PARA_MODERACION:
            detalle = conciliacion.detalle
    evento.procesado_en = ahora
    evento.error = detalle
    await session.flush()
    return True


async def registrar_fallo(
    session: AsyncSession, evento_id: uuid.UUID, error_tipo: str
) -> None:
    """Solo el nombre del tipo de la excepcion: el mensaje puede traer datos de
    la pasarela."""
    await session.execute(
        update(EventoPasarela)
        .where(EventoPasarela.id == evento_id)
        .values(intentos=EventoPasarela.intentos + 1, error=error_tipo)
    )
    await session.flush()


async def pendientes(
    session: AsyncSession, *, ahora: datetime
) -> tuple[uuid.UUID, ...]:
    """Los que el barrido reintenta: sin procesar, con intentos y con un
    minuto desde que llegaron, los mas viejos primero."""
    stmt = (
        select(EventoPasarela.id)
        .where(
            EventoPasarela.procesado_en.is_(None),
            EventoPasarela.intentos < INTENTOS_MAXIMOS_EVENTO,
            EventoPasarela.created_at <= ahora - ESPERA_REINTENTO_EVENTO,
        )
        .order_by(EventoPasarela.created_at)
        .limit(TOPE_PENDIENTES)
    )
    return tuple((await session.execute(stmt)).scalars())


async def con_error(
    session: AsyncSession, parametros: ParametrosPagina
) -> tuple[list[EventoPasarela], str | None]:
    """Para moderacion, del mas nuevo al mas viejo: discrepancias, eventos sin
    cobro y los que fallan o agotaron los intentos."""
    stmt = select(EventoPasarela).where(EventoPasarela.error.is_not(None))
    return await traer_pagina(session, stmt, EventoPasarela, parametros)
