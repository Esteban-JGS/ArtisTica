from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.posts import PostCreate, PostResponse
from src.models.users import Profile

router = APIRouter()

@router.post("/", response_model=PostResponse)
async def create_post(
    post_in: PostCreate,
    current_user: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Crear un nuevo post."""
    # TODO: Insertar post, procesar pgvector embeddings asincronamente (worker)
    pass

@router.get("/", response_model=List[PostResponse])
async def get_feed(
    session: AsyncSession = Depends(get_db)
):
    """Obtener feed de posts, utilizando pgvector para similitud o simple orden cronológico."""
    # TODO: Fetch feed from DB
    pass
