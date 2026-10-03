"""Endpoints de perfiles, planes y onboarding de la pasarela.

Cada handler cierra la transaccion con commit despues de llamar al servicio.
Las rutas /perfiles/yo van antes que /perfiles/{handle}.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import (
    get_current_artista,
    get_current_user,
    get_current_user_id,
    get_db,
    get_pasarela,
)
from src.core.config import settings
from src.core.exceptions import ResourceNotFound
from src.domain import perfiles as dominio
from src.domain.politicas import PoliticasPedido
from src.models import Profile
from src.payments.contrato import PasarelaDePagos
from src.schemas.perfiles import (
    ActualizacionPerfil,
    CambioPlan,
    EstadoOnboardingRespuesta,
    PerfilPropio,
    PerfilPublico,
    RegistroPerfil,
    ResultadoPlan,
)
from src.services import perfiles as servicio

router = APIRouter(prefix="/perfiles", tags=["perfiles"])


def _politicas() -> PoliticasPedido:
    return PoliticasPedido.desde_config(settings)


@router.post("", response_model=PerfilPropio, status_code=status.HTTP_201_CREATED)
async def registrar_perfil(
    datos: RegistroPerfil,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> PerfilPropio:
    perfil = await servicio.registrar(session, user_id, datos.handle, datos.nombre)
    await session.commit()
    return PerfilPropio.desde(perfil, _politicas())


@router.get("/yo", response_model=PerfilPropio)
async def obtener_mi_perfil(
    perfil: Profile = Depends(get_current_user),
) -> PerfilPropio:
    return PerfilPropio.desde(perfil, _politicas())


@router.patch("/yo", response_model=PerfilPropio)
async def actualizar_mi_perfil(
    datos: ActualizacionPerfil,
    perfil: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PerfilPropio:
    perfil = await servicio.actualizar(
        session, perfil, datos.model_dump(exclude_unset=True)
    )
    await session.commit()
    return PerfilPropio.desde(perfil, _politicas())


@router.post("/yo/artista", response_model=PerfilPropio)
async def hacerse_artista(
    perfil: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PerfilPropio:
    perfil = await servicio.hacerse_artista(session, perfil)
    await session.commit()
    return PerfilPropio.desde(perfil, _politicas())


@router.put("/yo/plan", response_model=ResultadoPlan)
async def cambiar_plan(
    datos: CambioPlan,
    artista: Profile = Depends(get_current_artista),
    session: AsyncSession = Depends(get_db),
    pasarela: PasarelaDePagos = Depends(get_pasarela),
) -> ResultadoPlan:
    resultado = await servicio.cambiar_plan(
        session, pasarela, artista.id, datos.plan, _politicas()
    )
    await session.commit()
    return ResultadoPlan(
        plan=resultado.plan,
        tarifa_porcentaje=resultado.tarifa_porcentaje,
        tarifa_sincronizada=resultado.tarifa_sincronizada,
    )


@router.post("/yo/onboarding", response_model=EstadoOnboardingRespuesta)
async def iniciar_onboarding(
    artista: Profile = Depends(get_current_artista),
    session: AsyncSession = Depends(get_db),
    pasarela: PasarelaDePagos = Depends(get_pasarela),
) -> EstadoOnboardingRespuesta:
    cuenta = await servicio.iniciar_onboarding(
        session, pasarela, artista.id, _politicas()
    )
    await session.commit()
    return EstadoOnboardingRespuesta(
        estado=artista.pasarela_onboarding,
        url_onboarding=cuenta.url_onboarding,
        puede_cobrar=dominio.puede_cobrar(artista),
    )


@router.get("/yo/onboarding", response_model=EstadoOnboardingRespuesta)
async def consultar_onboarding(
    artista: Profile = Depends(get_current_artista),
    session: AsyncSession = Depends(get_db),
    pasarela: PasarelaDePagos = Depends(get_pasarela),
) -> EstadoOnboardingRespuesta:
    perfil = await servicio.sincronizar_onboarding(session, pasarela, artista.id)
    await session.commit()
    return EstadoOnboardingRespuesta(
        estado=perfil.pasarela_onboarding,
        url_onboarding=None,
        puede_cobrar=dominio.puede_cobrar(perfil),
    )


@router.get("/{handle}", response_model=PerfilPublico)
async def obtener_perfil_publico(
    handle: str,
    session: AsyncSession = Depends(get_db),
) -> PerfilPublico:
    stmt = select(Profile).where(Profile.handle == handle.strip().lower())
    perfil = (await session.execute(stmt)).scalar_one_or_none()
    if perfil is None:
        raise ResourceNotFound("Perfil no encontrado")
    return PerfilPublico.desde(perfil)
