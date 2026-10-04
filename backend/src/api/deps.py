import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.core.security import verify_token
from src.models.users import Profile, RolPerfil
from src.payments.contrato import PasarelaDePagos
from src.payments.fabrica import obtener_pasarela
from src.storage import Almacenamiento, obtener_almacenamiento

security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia para inyectar la sesión asíncrona de base de datos."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Extrae el JWT y devuelve el payload verificado sin consultar la DB."""
    # verify_token puede ir a la red por el JWKS: no se bloquea el loop
    return await run_in_threadpool(verify_token, credentials.credentials)


async def get_current_user_id(
    payload: dict = Depends(get_current_user_payload),
) -> uuid.UUID:
    """El id del usuario segun el token. Sirve antes de que exista el perfil."""
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador (sub)",
        )
    try:
        return uuid.UUID(str(user_id_str))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="ID de usuario malformado"
        ) from e


async def get_current_user(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> Profile:
    """Carga el perfil del usuario. El 404 le indica a la app que mande al registro."""
    profile = await session.get(Profile, user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Perfil no registrado"
        )
    return profile


async def get_current_artista(
    current_user: Profile = Depends(get_current_user),
) -> Profile:
    """Dependencia para endpoints que requieren rol de artista."""
    if current_user.rol != RolPerfil.ARTISTA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Solo para artistas"
        )
    return current_user


async def get_current_admin(
    current_user: Profile = Depends(get_current_user),
) -> Profile:
    """Dependencia para endpoints que requieren rol de administrador."""
    if current_user.rol != RolPerfil.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
        )
    return current_user


def get_pasarela() -> PasarelaDePagos:
    """La pasarela del proceso. Las pruebas la sobrescriben con una falsa."""
    return obtener_pasarela()


def get_almacenamiento() -> Almacenamiento:
    """El almacenamiento del proceso. Las pruebas lo sobrescriben con uno falso."""
    return obtener_almacenamiento()
