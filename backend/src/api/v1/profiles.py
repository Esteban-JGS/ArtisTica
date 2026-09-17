from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.profiles import ProfileResponse
from src.models.users import Profile

router = APIRouter()

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Obtener el perfil del usuario autenticado."""
    # TODO: Devolver el perfil actual
    return current_user

@router.get("/me/balance")
async def get_my_balance(
    current_user: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Calcula el saldo del usuario sumando las entradas del ledger."""
    # TODO: Consulta a ledger_entries sumando creditos y restando debitos
    pass
