from fastapi import APIRouter, Depends
import uuid
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.commissions import (
    CommissionCreate, CommissionResponse, 
    CommissionMessageCreate, CommissionMessageResponse
)
from src.models.users import Profile

router = APIRouter()

@router.post("/", response_model=CommissionResponse)
async def create_commission(
    request: CommissionCreate,
    current_user: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Iniciar un encargo (estado: solicitada)."""
    # TODO: Validar artista, crear encargo y registrar mensaje inicial si existe
    pass

@router.post("/{commission_id}/transition", response_model=CommissionResponse)
async def transition_commission_state(
    commission_id: uuid.UUID,
    new_state: str,
    current_user: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Transicionar el estado del encargo respetando la máquina de estados estricta."""
    # TODO: Validar permisos (cliente/artista), chequear COMMISSION_TRANSITIONS, y manejar ledger
    pass

@router.post("/{commission_id}/messages", response_model=CommissionMessageResponse)
async def send_commission_message(
    commission_id: uuid.UUID,
    message: CommissionMessageCreate,
    current_user: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Enviar mensaje dentro del chat de un encargo."""
    # TODO: Validar acceso al chat, insertar mensaje
    pass
