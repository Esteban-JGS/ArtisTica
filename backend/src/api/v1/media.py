from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.users import Profile
from src.schemas.media import (
    AssetRegisterRequest,
    MediaAssetResponse,
    SignedUrlResponse,
)

router = APIRouter()


@router.post("/upload-url", response_model=SignedUrlResponse)
async def generate_signed_url(
    type: str,
    current_user: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Generar URL firmada de Supabase Storage para subir un archivo directamente.
    El archivo nunca pasa por la API.
    """
    # TODO: Integrar cliente de Supabase Storage para generar signed URL


@router.post("/register", response_model=MediaAssetResponse)
async def register_asset(
    request: AssetRegisterRequest,
    current_user: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Registrar un asset que ya fue subido exitosamente a Supabase Storage."""
    # TODO: Validar existencia, encolar job de miniaturas/embeddings y crear registro
