"""Endpoints de perfiles, planes y onboarding de la pasarela.

Cada handler cierra la transaccion con commit despues de llamar al servicio.
Las rutas /perfiles/yo van antes que /perfiles/{handle}.
"""

from fastapi import APIRouter, status
from sqlalchemy import select

from src.api.deps import Artista, IdUsuario, Pasarela, Sesion, Usuario
from src.core.config import settings
from src.core.exceptions import ResourceNotFound
from src.domain import perfiles as dominio
from src.domain.politicas import PoliticasPedido
from src.models import Profile
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


@router.post("", status_code=status.HTTP_201_CREATED)
async def registrar_perfil(
    datos: RegistroPerfil,
    user_id: IdUsuario,
    session: Sesion,
) -> PerfilPropio:
    perfil = await servicio.registrar(session, user_id, datos.handle, datos.nombre)
    await session.commit()
    return PerfilPropio.desde(perfil, _politicas())


@router.get("/yo")
async def obtener_mi_perfil(
    perfil: Usuario,
) -> PerfilPropio:
    return PerfilPropio.desde(perfil, _politicas())


@router.patch("/yo")
async def actualizar_mi_perfil(
    datos: ActualizacionPerfil,
    perfil: Usuario,
    session: Sesion,
) -> PerfilPropio:
    perfil = await servicio.actualizar(
        session, perfil, datos.model_dump(exclude_unset=True)
    )
    await session.commit()
    return PerfilPropio.desde(perfil, _politicas())


@router.post("/yo/artista")
async def hacerse_artista(
    perfil: Usuario,
    session: Sesion,
) -> PerfilPropio:
    perfil = await servicio.hacerse_artista(session, perfil)
    await session.commit()
    return PerfilPropio.desde(perfil, _politicas())


@router.put("/yo/plan")
async def cambiar_plan(
    datos: CambioPlan,
    artista: Artista,
    session: Sesion,
    pasarela: Pasarela,
) -> ResultadoPlan:
    resultado = await servicio.cambiar_plan(
        session,
        pasarela,
        artista.id,
        datos.plan,
        _politicas(),
        settings.ESTUDIO_AUTOSERVICIO,
    )
    await session.commit()
    return ResultadoPlan(
        plan=resultado.plan,
        tarifa_porcentaje=resultado.tarifa_porcentaje,
        tarifa_sincronizada=resultado.tarifa_sincronizada,
    )


@router.post("/yo/onboarding")
async def iniciar_onboarding(
    artista: Artista,
    session: Sesion,
    pasarela: Pasarela,
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


@router.get("/yo/onboarding")
async def consultar_onboarding(
    artista: Artista,
    session: Sesion,
    pasarela: Pasarela,
) -> EstadoOnboardingRespuesta:
    perfil = await servicio.sincronizar_onboarding(session, pasarela, artista.id)
    await session.commit()
    return EstadoOnboardingRespuesta(
        estado=perfil.pasarela_onboarding,
        url_onboarding=None,
        puede_cobrar=dominio.puede_cobrar(perfil),
    )


@router.get("/{handle}")
async def obtener_perfil_publico(
    handle: str,
    session: Sesion,
) -> PerfilPublico:
    stmt = select(Profile).where(Profile.handle == handle.strip().lower())
    perfil = (await session.execute(stmt)).scalar_one_or_none()
    if perfil is None:
        raise ResourceNotFound("Perfil no encontrado")
    return PerfilPublico.desde(perfil)
