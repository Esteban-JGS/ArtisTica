from fastapi import APIRouter

from src.api.v1 import (
    busqueda,
    catalogo,
    comentarios,
    consultas,
    medios,
    perfiles,
    publicaciones,
    social,
)

api_router = APIRouter()
api_router.include_router(perfiles.router)
api_router.include_router(medios.router)
api_router.include_router(catalogo.router)
api_router.include_router(publicaciones.router)
api_router.include_router(social.router)
api_router.include_router(comentarios.router)
api_router.include_router(busqueda.router)
api_router.include_router(consultas.router)
