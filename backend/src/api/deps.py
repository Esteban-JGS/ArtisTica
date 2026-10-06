import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

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

Credenciales = Annotated[HTTPAuthorizationCredentials, Depends(security)]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia para inyectar la sesión asíncrona de base de datos."""
    async with AsyncSessionLocal() as session:
        yield session


Sesion = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_payload(credentials: Credenciales) -> dict:
    """Extrae el JWT y devuelve el payload verificado sin consultar la DB."""
    # verify_token puede ir a la red por el JWKS: no se bloquea el loop
    return await run_in_threadpool(verify_token, credentials.credentials)


PayloadToken = Annotated[dict, Depends(get_current_user_payload)]


async def get_current_user_id(payload: PayloadToken) -> uuid.UUID:
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


IdUsuario = Annotated[uuid.UUID, Depends(get_current_user_id)]


async def get_current_user(user_id: IdUsuario, session: Sesion) -> Profile:
    """Carga el perfil del usuario. El 404 le indica a la app que mande al registro."""
    profile = await session.get(Profile, user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Perfil no registrado"
        )
    return profile


Usuario = Annotated[Profile, Depends(get_current_user)]


async def get_current_artista(current_user: Usuario) -> Profile:
    """Dependencia para endpoints que requieren rol de artista."""
    if current_user.rol != RolPerfil.ARTISTA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Solo para artistas"
        )
    return current_user


Artista = Annotated[Profile, Depends(get_current_artista)]


async def get_current_admin(current_user: Usuario) -> Profile:
    """Dependencia para endpoints que requieren rol de administrador."""
    if current_user.rol != RolPerfil.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
        )
    return current_user


Admin = Annotated[Profile, Depends(get_current_admin)]


def get_pasarela() -> PasarelaDePagos:
    """La pasarela del proceso. Las pruebas la sobrescriben con una falsa."""
    return obtener_pasarela()


Pasarela = Annotated[PasarelaDePagos, Depends(get_pasarela)]


def get_almacenamiento() -> Almacenamiento:
    """El almacenamiento del proceso. Las pruebas lo sobrescriben con uno falso."""
    return obtener_almacenamiento()


AlmacenamientoDeMedios = Annotated[Almacenamiento, Depends(get_almacenamiento)]
