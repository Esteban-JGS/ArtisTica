"""Endpoints del catalogo: obras y servicios del artista.

Cada handler cierra la transaccion con commit despues de llamar al servicio.
Las rutas /servicios/mios van antes que /servicios/{servicio_id}.
La galeria y la vitrina de un artista son publicas: no piden token.
"""

import uuid

from fastapi import APIRouter, Response, status

from src.api.deps import AlmacenamientoDeMedios, Artista, Sesion
from src.api.paginacion import Pagina, Paginacion
from src.core.config import settings
from src.domain.catalogo import LimitesPlan
from src.schemas.catalogo import (
    LimitesRespuesta,
    ObraActualizacion,
    ObraNueva,
    ObraRespuesta,
    ServicioActualizacion,
    ServicioNuevo,
    ServicioRespuesta,
)
from src.services import catalogo as servicio

router = APIRouter(tags=["catalogo"])


def _limites() -> LimitesPlan:
    return LimitesPlan.desde_config(settings)


# Obras


@router.post("/obras", status_code=status.HTTP_201_CREATED)
async def crear_obra(
    datos: ObraNueva,
    artista: Artista,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> ObraRespuesta:
    detalle = await servicio.crear_obra(
        session,
        artista,
        datos.model_dump(exclude_unset=True),
        limites=_limites(),
        monto_minimo=settings.MONTO_MINIMO_PEDIDO,
    )
    await session.commit()
    return ObraRespuesta.desde(detalle, almacenamiento)


@router.get("/obras/{obra_id}")
async def obtener_obra(
    obra_id: uuid.UUID,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> ObraRespuesta:
    detalle = await servicio.obtener_obra(session, obra_id)
    return ObraRespuesta.desde(detalle, almacenamiento)


@router.patch("/obras/{obra_id}")
async def editar_obra(
    obra_id: uuid.UUID,
    datos: ObraActualizacion,
    artista: Artista,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> ObraRespuesta:
    detalle = await servicio.editar_obra(
        session,
        artista,
        obra_id,
        datos.model_dump(exclude_unset=True),
        limites=_limites(),
        monto_minimo=settings.MONTO_MINIMO_PEDIDO,
    )
    await session.commit()
    return ObraRespuesta.desde(detalle, almacenamiento)


@router.delete("/obras/{obra_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_obra(
    obra_id: uuid.UUID,
    artista: Artista,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> Response:
    await servicio.eliminar_obra(session, almacenamiento, artista, obra_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/artistas/{handle}/obras")
async def listar_obras_del_artista(
    handle: str,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
    paginacion: Paginacion,
) -> Pagina[ObraRespuesta]:
    detalles, siguiente = await servicio.listar_obras_de(session, handle, paginacion)
    return Pagina(
        items=[ObraRespuesta.desde(d, almacenamiento) for d in detalles],
        siguiente_cursor=siguiente,
    )


# Servicios


@router.post("/servicios", status_code=status.HTTP_201_CREATED)
async def crear_servicio(
    datos: ServicioNuevo,
    artista: Artista,
    session: Sesion,
) -> ServicioRespuesta:
    detalle = await servicio.crear_servicio(
        session,
        artista,
        datos.model_dump(exclude_unset=True),
        limites=_limites(),
        monto_minimo=settings.MONTO_MINIMO_PEDIDO,
    )
    await session.commit()
    return ServicioRespuesta.desde(detalle)


@router.get("/servicios/mios")
async def listar_mis_servicios(
    artista: Artista,
    session: Sesion,
    paginacion: Paginacion,
) -> Pagina[ServicioRespuesta]:
    detalles, siguiente = await servicio.listar_servicios_propios(
        session, artista, paginacion
    )
    return Pagina(
        items=[ServicioRespuesta.desde(d) for d in detalles], siguiente_cursor=siguiente
    )


@router.get("/servicios/{servicio_id}")
async def obtener_servicio(
    servicio_id: uuid.UUID,
    session: Sesion,
) -> ServicioRespuesta:
    detalle = await servicio.obtener_servicio(session, servicio_id)
    return ServicioRespuesta.desde(detalle)


@router.patch("/servicios/{servicio_id}")
async def editar_servicio(
    servicio_id: uuid.UUID,
    datos: ServicioActualizacion,
    artista: Artista,
    session: Sesion,
) -> ServicioRespuesta:
    detalle = await servicio.editar_servicio(
        session,
        artista,
        servicio_id,
        datos.model_dump(exclude_unset=True),
        limites=_limites(),
        monto_minimo=settings.MONTO_MINIMO_PEDIDO,
    )
    await session.commit()
    return ServicioRespuesta.desde(detalle)


@router.delete("/servicios/{servicio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_servicio(
    servicio_id: uuid.UUID,
    artista: Artista,
    session: Sesion,
) -> Response:
    await servicio.eliminar_servicio(session, artista, servicio_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/artistas/{handle}/servicios")
async def listar_servicios_del_artista(
    handle: str,
    session: Sesion,
    paginacion: Paginacion,
) -> Pagina[ServicioRespuesta]:
    detalles, siguiente = await servicio.listar_servicios_de(
        session, handle, paginacion
    )
    return Pagina(
        items=[ServicioRespuesta.desde(d) for d in detalles], siguiente_cursor=siguiente
    )


# Limites del plan


@router.get("/catalogo/limites")
async def obtener_limites(
    artista: Artista,
    session: Sesion,
) -> LimitesRespuesta:
    return LimitesRespuesta.desde(
        await servicio.limites_de(session, artista, _limites())
    )
