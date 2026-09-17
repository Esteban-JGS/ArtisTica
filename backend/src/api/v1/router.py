from fastapi import APIRouter
from . import profiles, posts, media, commissions

api_router = APIRouter()

api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(commissions.router, prefix="/commissions", tags=["commissions"])
