from fastapi import APIRouter

from src.api.v1 import catalogo, medios, perfiles

api_router = APIRouter()
api_router.include_router(perfiles.router)
api_router.include_router(medios.router)
api_router.include_router(catalogo.router)
