"""Endpoints de moderacion: disputas abiertas, su evidencia y su resolucion.

Todos exigen un perfil admin: un cliente, un artista o un tercero reciben 403.
Ninguna respuesta lleva la referencia de la pasarela ni una url de
autenticacion.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter

from src.api.deps import Admin, AlmacenamientoDeMedios, Pasarela, Sesion
from src.api.paginacion import Pagina, Paginacion
from src.core.config import settings
from src.domain.politicas import PoliticasPedido
from src.schemas.pedidos import MensajeModeracion, PedidoRespuesta, ResolucionDisputa
from src.services import consultas, contratacion
from src.services import pedidos as servicio

router = APIRouter(prefix="/moderacion", tags=["moderacion"])


@router.get("/disputas")
async def disputas_abiertas(
    _admin: Admin,
    session: Sesion,
    paginacion: Paginacion,
    almacenamiento: AlmacenamientoDeMedios,
) -> Pagina[PedidoRespuesta]:
    """De la disputa mas vieja a la mas nueva."""
    detalles, siguiente = await servicio.disputas_abiertas(session, paginacion)
    return Pagina(
        items=[PedidoRespuesta.desde(d, almacenamiento) for d in detalles],
        siguiente_cursor=siguiente,
    )


@router.get("/pedidos/{pedido_id}")
async def detalle(
    pedido_id: uuid.UUID,
    _admin: Admin,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    return PedidoRespuesta.desde(
        await servicio.detalle_para_moderacion(session, pedido_id), almacenamiento
    )


@router.get("/pedidos/{pedido_id}/mensajes")
async def mensajes(
    pedido_id: uuid.UUID,
    _admin: Admin,
    session: Sesion,
    paginacion: Paginacion,
) -> Pagina[MensajeModeracion]:
    """El chat de la consulta del pedido, del mas viejo al mas nuevo."""
    detalles, siguiente = await consultas.mensajes_para_moderacion(
        session, pedido_id, paginacion
    )
    return Pagina(
        items=[MensajeModeracion.desde(d) for d in detalles],
        siguiente_cursor=siguiente,
    )


@router.post("/pedidos/{pedido_id}/disputa/resolver")
async def resolver_disputa(
    pedido_id: uuid.UUID,
    datos: ResolucionDisputa,
    admin: Admin,
    session: Sesion,
    pasarela: Pasarela,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    detalle_ = await contratacion.resolver_disputa(
        session,
        pasarela,
        admin,
        pedido_id,
        destino=datos.destino,
        resolucion=datos.resolucion,
        reembolsos=datos.reembolsos_por_cobro(),
        ahora=datetime.now(UTC),
        politicas=PoliticasPedido.desde_config(settings),
    )
    await session.commit()
    return PedidoRespuesta.desde(detalle_, almacenamiento)
