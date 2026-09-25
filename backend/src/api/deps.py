import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.core.security import verify_token
from src.models.users import Profile, RolPerfil

security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia para inyectar la sesión asíncrona de base de datos."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Extrae el JWT y devuelve el payload verificado sin consultar la DB."""
    return verify_token(credentials.credentials)


async def get_current_user(
    payload: dict = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db),
) -> Profile:
    """Extrae el 'sub' del token y carga el perfil del usuario desde la DB."""
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador (sub)",
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="ID de usuario malformado"
        )

    profile = await session.get(Profile, user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de usuario no existe"
        )

    return profile


async def get_current_admin(
    current_user: Profile = Depends(get_current_user),
) -> Profile:
    """Dependencia para endpoints que requieren rol de administrador."""
    if current_user.rol != RolPerfil.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
        )
    return current_user
