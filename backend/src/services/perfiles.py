"""Perfiles, roles, planes y onboarding de la pasarela sobre la base.

No cierra la transaccion: hace flush, y la abre y la cierra quien llama.
La fila de `profiles` con SELECT ... FOR UPDATE es el bloqueo por artista:
todo lo que cambia la tarifa de la cuenta conectada lo hace con el tomado.
"""

import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    ActorNoAutorizado,
    CobroNoHabilitado,
    HandleNoDisponible,
    PerfilYaRegistrado,
    ReglaDeNegocioViolada,
    ResourceNotFound,
)
from src.domain import perfiles as dominio
from src.domain.pedidos import ESTADOS_TERMINALES, tarifa_para_plan
from src.domain.politicas import PoliticasPedido
from src.models import EstadoOnboarding, Pedido, PlanArtista, Profile, RolPerfil
from src.payments.contrato import CuentaConectada, EstadoCuenta, PasarelaDePagos
from src.payments.errores import ErrorPasarela

logger = logging.getLogger(__name__)

INDICE_HANDLE = "ix_profiles_handle"
LLAVE_PERFIL = "profiles_pkey"
CAMPOS_EDITABLES = frozenset({"handle", "nombre", "bio", "categorias", "provincia"})

_ONBOARDING_POR_ESTADO = {
    EstadoCuenta.PENDIENTE: EstadoOnboarding.PENDIENTE,
    EstadoCuenta.COMPLETADA: EstadoOnboarding.COMPLETADO,
    EstadoCuenta.RECHAZADA: EstadoOnboarding.RECHAZADO,
}


@dataclass(frozen=True)
class ResultadoCambioPlan:
    plan: PlanArtista
    tarifa_porcentaje: Decimal
    # None: no hay cuenta, o quedo pendiente por pedidos abiertos con otra tarifa
    tarifa_sincronizada: bool | None


# Carga y bloqueo


async def bloquear_perfil(session: AsyncSession, perfil_id: uuid.UUID) -> Profile:
    stmt = (
        select(Profile)
        .where(Profile.id == perfil_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    perfil = (await session.execute(stmt)).scalar_one_or_none()
    if perfil is None:
        raise ResourceNotFound(f"profiles {perfil_id} no existe")
    return perfil


def _restriccion(exc: IntegrityError) -> str | None:
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


# Registro y edicion


async def registrar(
    session: AsyncSession, perfil_id: uuid.UUID, handle: str, nombre: str
) -> Profile:
    if await session.get(Profile, perfil_id) is not None:
        raise PerfilYaRegistrado("El perfil ya esta registrado")
    perfil = Profile(
        id=perfil_id,
        handle=handle,
        nombre=nombre,
        categorias=[],
        rol=RolPerfil.PUBLICO,
        plan=PlanArtista.TALLER,
        is_verified=False,
        pasarela_onboarding=EstadoOnboarding.NO_INICIADO,
    )
    try:
        async with session.begin_nested():
            session.add(perfil)
            await session.flush()
    except IntegrityError as exc:
        restriccion = _restriccion(exc)
        if restriccion == INDICE_HANDLE:
            raise HandleNoDisponible("Ese handle ya esta en uso") from exc
        if restriccion == LLAVE_PERFIL:
            # Dos registros simultaneos con el mismo id
            raise PerfilYaRegistrado("El perfil ya esta registrado") from exc
        raise
    return perfil


async def actualizar(
    session: AsyncSession, perfil: Profile, cambios: Mapping[str, Any]
) -> Profile:
    desconocidos = set(cambios) - CAMPOS_EDITABLES
    if desconocidos:
        raise ValueError(f"Campos no editables: {sorted(desconocidos)}")
    # begin_nested hace flush antes del savepoint: los cambios van adentro, para
    # que un handle repetido no rompa la transaccion externa
    try:
        async with session.begin_nested():
            for campo, valor in cambios.items():
                setattr(perfil, campo, valor)
            await session.flush()
    except IntegrityError as exc:
        if _restriccion(exc) == INDICE_HANDLE:
            raise HandleNoDisponible("Ese handle ya esta en uso") from exc
        raise
    return perfil


async def hacerse_artista(session: AsyncSession, perfil: Profile) -> Profile:
    if perfil.rol == RolPerfil.ADMIN:
        raise ReglaDeNegocioViolada("Un administrador no se registra como artista")
    if perfil.rol == RolPerfil.ARTISTA:
        return perfil
    perfil.rol = RolPerfil.ARTISTA
    perfil.plan = PlanArtista.TALLER
    await session.flush()
    return perfil


# Plan


async def _tarifas_abiertas(
    session: AsyncSession, artista_id: uuid.UUID
) -> list[Decimal]:
    stmt = select(Pedido.tarifa_porcentaje).where(
        Pedido.artista_id == artista_id,
        Pedido.estado.not_in(ESTADOS_TERMINALES),
    )
    return list((await session.execute(stmt)).scalars())


async def cambiar_plan(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    perfil_id: uuid.UUID,
    plan: PlanArtista,
    politicas: PoliticasPedido,
    estudio_autoservicio: bool,
) -> ResultadoCambioPlan:
    # Sin autoservicio, Estudio llega por la suscripcion. Bajar a Taller siempre.
    if plan == PlanArtista.ESTUDIO and not estudio_autoservicio:
        raise ActorNoAutorizado("El plan Estudio se activa con la suscripcion")
    perfil = await bloquear_perfil(session, perfil_id)
    if perfil.rol != RolPerfil.ARTISTA:
        raise ActorNoAutorizado("Solo un artista tiene plan")
    tarifa = tarifa_para_plan(plan, politicas)
    if perfil.plan == plan:
        return ResultadoCambioPlan(
            plan=plan, tarifa_porcentaje=tarifa, tarifa_sincronizada=None
        )

    perfil.plan = plan
    await session.flush()

    sincronizada: bool | None = None
    if perfil.pasarela_cuenta_id is not None:
        tarifas = await _tarifas_abiertas(session, perfil.id)
        fija = dominio.tarifa_fija_de_cuenta(plan, tarifas, politicas)
        if fija is not None:
            # Con el bloqueo tomado: no se cruza con un cobro del lote 8
            try:
                await pasarela.configurar_tarifa(perfil.pasarela_cuenta_id, fija)
                sincronizada = True
            except ErrorPasarela as exc:
                # El plan se conserva: el lote 8 ajusta la tarifa antes de cobrar
                logger.warning(
                    "No se pudo fijar la tarifa de la cuenta del perfil %s: %s",
                    perfil.id,
                    type(exc).__name__,
                )
                sincronizada = False
    return ResultadoCambioPlan(
        plan=plan, tarifa_porcentaje=tarifa, tarifa_sincronizada=sincronizada
    )


# Onboarding de la pasarela


def aplicar_estado_cuenta(perfil: Profile, estado: EstadoCuenta) -> None:
    """Unica via que cambia `is_verified`. La usa tambien el webhook del lote 9."""
    onboarding = _ONBOARDING_POR_ESTADO[estado]
    perfil.pasarela_onboarding = onboarding
    perfil.is_verified = onboarding == EstadoOnboarding.COMPLETADO


async def iniciar_onboarding(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    perfil_id: uuid.UUID,
    politicas: PoliticasPedido,
) -> CuentaConectada:
    # El bloqueo evita que dos llamadas simultaneas creen dos cuentas
    perfil = await bloquear_perfil(session, perfil_id)
    if perfil.rol != RolPerfil.ARTISTA:
        raise ActorNoAutorizado("Solo un artista conecta una cuenta de cobro")
    if perfil.pasarela_onboarding == EstadoOnboarding.RECHAZADO:
        raise ReglaDeNegocioViolada(
            "La pasarela rechazo la verificacion. Escribinos a soporte para revisarla"
        )

    if perfil.pasarela_cuenta_id is None:
        # La clave es del perfil: si el commit falla, el reintento no crea
        # una segunda cuenta en la pasarela
        cuenta = await pasarela.crear_cuenta_conectada(
            nombre=perfil.nombre,
            tarifa_porcentaje=tarifa_para_plan(perfil.plan, politicas),
            clave_idempotencia=f"cuenta-conectada-{perfil.id}",
            metadatos={"perfil_id": str(perfil.id)},
        )
        perfil.pasarela_cuenta_id = cuenta.id
    else:
        cuenta = await pasarela.consultar_cuenta(perfil.pasarela_cuenta_id)
    aplicar_estado_cuenta(perfil, cuenta.estado)
    await session.flush()
    # La url_onboarding solo viaja en la respuesta al dueno
    return cuenta


async def sincronizar_onboarding(
    session: AsyncSession, pasarela: PasarelaDePagos, perfil_id: uuid.UUID
) -> Profile:
    perfil = await bloquear_perfil(session, perfil_id)
    if perfil.pasarela_cuenta_id is None:
        return perfil
    cuenta = await pasarela.consultar_cuenta(perfil.pasarela_cuenta_id)
    aplicar_estado_cuenta(perfil, cuenta.estado)
    await session.flush()
    return perfil


def exigir_cobro_habilitado(perfil: Profile) -> None:
    """La llama el lote 8 antes del primer cobro."""
    if not dominio.puede_cobrar(perfil):
        raise CobroNoHabilitado(
            "El artista tiene que completar la verificacion de la pasarela para cobrar"
        )
