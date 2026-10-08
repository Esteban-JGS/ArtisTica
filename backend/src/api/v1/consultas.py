"""Endpoints de consultas y de su chat.

Todos piden token; cualquier rol puede ser cliente. No hay tiempo real: la app
pide cada pocos segundos los mensajes nuevos y el resumen de no leidos.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from src.api.deps import Sesion, Usuario
from src.api.paginacion import Pagina, Paginacion
from src.core.config import settings
from src.domain.consultas import LimitesConsultas, RolEnConsulta
from src.domain.enums import EstadoConsulta
from src.schemas.consultas import (
    ConsultaRespuesta,
    MensajeRespuesta,
    NuevaConsulta,
    NuevoMensaje,
    ResumenNoLeidos,
)
from src.services import consultas as servicio

router = APIRouter(prefix="/consultas", tags=["consultas"])

SIN_CONTENIDO = status.HTTP_204_NO_CONTENT


@router.post("", status_code=status.HTTP_201_CREATED)
async def abrir_consulta(
    datos: NuevaConsulta, usuario: Usuario, session: Sesion, response: Response
) -> ConsultaRespuesta:
    """201 si se creo; 200 si el mensaje se agrego a una en curso igual."""
    detalle, creada = await servicio.abrir(
        session,
        usuario,
        artista_id=datos.artista_id,
        servicio_id=datos.servicio_id,
        obra_id=datos.obra_id,
        texto=datos.texto,
        presupuesto=datos.presupuesto,
        fecha_deseada=datos.fecha_deseada,
        ahora=datetime.now(UTC),
        limites=LimitesConsultas.desde_config(settings),
    )
    await session.commit()
    if not creada:
        response.status_code = status.HTTP_200_OK
    return ConsultaRespuesta.desde(detalle)


@router.get("")
async def bandeja(
    usuario: Usuario,
    session: Sesion,
    paginacion: Paginacion,
    como: RolEnConsulta | None = None,
    estado: EstadoConsulta | None = None,
) -> Pagina[ConsultaRespuesta]:
    detalles, siguiente = await servicio.bandeja(
        session, usuario, como, estado, paginacion
    )
    return Pagina(
        items=[ConsultaRespuesta.desde(d) for d in detalles],
        siguiente_cursor=siguiente,
    )


# Antes que /{consulta_id}: si no, la capturaria


@router.get("/no-leidos")
async def resumen_no_leidos(usuario: Usuario, session: Sesion) -> ResumenNoLeidos:
    consultas, mensajes = await servicio.resumen_no_leidos(session, usuario)
    return ResumenNoLeidos(consultas=consultas, mensajes=mensajes)


@router.get("/{consulta_id}")
async def detalle(
    consulta_id: uuid.UUID, usuario: Usuario, session: Sesion
) -> ConsultaRespuesta:
    return ConsultaRespuesta.desde(
        await servicio.detalle(session, usuario, consulta_id)
    )


@router.post("/{consulta_id}/descartar")
async def descartar(
    consulta_id: uuid.UUID, usuario: Usuario, session: Sesion
) -> ConsultaRespuesta:
    detalle = await servicio.descartar(session, usuario, consulta_id)
    await session.commit()
    return ConsultaRespuesta.desde(detalle)


@router.put("/{consulta_id}/leido", status_code=SIN_CONTENIDO)
async def marcar_leido(
    consulta_id: uuid.UUID, usuario: Usuario, session: Sesion
) -> Response:
    await servicio.marcar_leido(session, usuario, consulta_id)
    await session.commit()
    return Response(status_code=SIN_CONTENIDO)


# Mensajes


@router.get("/{consulta_id}/mensajes")
async def historial(
    consulta_id: uuid.UUID, usuario: Usuario, session: Sesion, paginacion: Paginacion
) -> Pagina[MensajeRespuesta]:
    """Del mas nuevo al mas viejo."""
    detalles, siguiente = await servicio.listar_mensajes(
        session, usuario, consulta_id, paginacion
    )
    return Pagina(
        items=[MensajeRespuesta.desde(d) for d in detalles],
        siguiente_cursor=siguiente,
    )


@router.get("/{consulta_id}/mensajes/nuevos")
async def mensajes_nuevos(
    consulta_id: uuid.UUID, usuario: Usuario, session: Sesion, paginacion: Paginacion
) -> Pagina[MensajeRespuesta]:
    """Los posteriores a `cursor`, del mas viejo al mas nuevo.

    La app manda el `cursor` de su ultimo mensaje; si la pagina se llena,
    sigue con `siguiente_cursor`.
    """
    detalles, siguiente = await servicio.mensajes_nuevos(
        session, usuario, consulta_id, paginacion
    )
    return Pagina(
        items=[MensajeRespuesta.desde(d) for d in detalles],
        siguiente_cursor=siguiente,
    )


@router.post("/{consulta_id}/mensajes", status_code=status.HTTP_201_CREATED)
async def enviar(
    consulta_id: uuid.UUID, datos: NuevoMensaje, usuario: Usuario, session: Sesion
) -> MensajeRespuesta:
    detalle = await servicio.enviar(
        session, usuario, consulta_id, datos.texto, datetime.now(UTC)
    )
    await session.commit()
    return MensajeRespuesta.desde(detalle)
