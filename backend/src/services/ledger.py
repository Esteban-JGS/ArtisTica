"""Ledger: una fila por cada captura y cada reembolso que la pasarela confirmo.

Solo agrega filas y hace flush, en la misma transaccion que cambia el cobro.
Nunca edita ni borra. La clave unica hace que un hecho se asiente una sola
vez. Lo que la pasarela no informa, como su costo de procesamiento, queda nulo.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.pedidos import porcentaje_de
from src.models import Cobro, LedgerEntry, Pedido

CAPTURA = "captura"
REEMBOLSO = "reembolso"


async def asentar_captura(
    session: AsyncSession, *, pedido: Pedido, cobro: Cobro, ahora: datetime
) -> LedgerEntry:
    fila = LedgerEntry(
        pedido_id=pedido.id,
        cobro_id=cobro.id,
        profile_id=pedido.artista_id,
        clave=f"{CAPTURA}-{cobro.id}",
        tipo_evento=CAPTURA,
        monto_bruto=cobro.monto,
        tarifa_artistica=porcentaje_de(cobro.monto, pedido.tarifa_porcentaje),
        costo_procesamiento=None,
        monto_neto_artista=None,
        referencia_pasarela=cobro.referencia_pasarela,
        ocurrido_en=ahora,
    )
    session.add(fila)
    await session.flush()
    return fila


async def asentar_reembolso(
    session: AsyncSession,
    *,
    pedido: Pedido,
    cobro: Cobro,
    monto: Decimal,
    ahora: datetime,
) -> LedgerEntry:
    """Con el cobro ya actualizado: la clave lleva el acumulado reembolsado
    despues de este reembolso. El monto va positivo: el tipo dice que es una
    devolucion."""
    fila = LedgerEntry(
        pedido_id=pedido.id,
        cobro_id=cobro.id,
        profile_id=pedido.artista_id,
        clave=f"{REEMBOLSO}-{cobro.id}-{cobro.monto_reembolsado}",
        tipo_evento=REEMBOLSO,
        monto_bruto=monto,
        tarifa_artistica=None,
        costo_procesamiento=None,
        monto_neto_artista=None,
        referencia_pasarela=cobro.referencia_pasarela,
        ocurrido_en=ahora,
    )
    session.add(fila)
    await session.flush()
    return fila
