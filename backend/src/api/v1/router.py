from fastapi import APIRouter

from src.api.v1 import medios, perfiles

api_router = APIRouter()
api_router.include_router(perfiles.router)
api_router.include_router(medios.router)
