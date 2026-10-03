from fastapi import APIRouter

from src.api.v1 import perfiles

api_router = APIRouter()
api_router.include_router(perfiles.router)
