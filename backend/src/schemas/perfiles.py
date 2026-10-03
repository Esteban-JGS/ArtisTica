"""Esquemas de perfiles. Las validaciones de forma llaman al dominio y dan 422."""

from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from src.domain import perfiles as dominio
from src.domain.pedidos import tarifa_para_plan
from src.domain.politicas import PoliticasPedido
from src.models.users import EstadoOnboarding, PlanArtista, Profile, RolPerfil


def _sin_contacto(texto: str) -> str:
    if dominio.contiene_contacto_prohibido(texto):
        raise ValueError(
            "No se permiten telefonos ni WhatsApp: el contacto va por la plataforma"
        )
    return texto


def _provincia_valida(provincia: str | None) -> str | None:
    if provincia is not None and provincia not in dominio.PROVINCIAS:
        raise ValueError(
            f"Provincia invalida. Opciones: {', '.join(dominio.PROVINCIAS)}"
        )
    return provincia


def _categorias_sin_repetir(categorias: list[str]) -> list[str]:
    if len({c.casefold() for c in categorias}) != len(categorias):
        raise ValueError("Hay categorias repetidas")
    return categorias


Handle = Annotated[str, AfterValidator(dominio.normalizar_handle)]
Nombre = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
    AfterValidator(_sin_contacto),
]
Bio = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=500),
    AfterValidator(_sin_contacto),
]
Categoria = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)
]
Categorias = Annotated[
    list[Categoria], Field(max_length=5), AfterValidator(_categorias_sin_repetir)
]
Provincia = Annotated[str | None, AfterValidator(_provincia_valida)]


# Entrada


class RegistroPerfil(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle: Handle
    nombre: Nombre


class ActualizacionPerfil(BaseModel):
    """Solo se aplican los campos presentes en el cuerpo."""

    model_config = ConfigDict(extra="forbid")

    handle: Handle | None = None
    nombre: Nombre | None = None
    bio: Bio | None = None
    categorias: Categorias | None = None
    provincia: Provincia = None

    @model_validator(mode="after")
    def _obligatorios_no_nulos(self) -> Self:
        for campo in ("handle", "nombre", "categorias"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"{campo} no puede ser nulo")
        return self


class CambioPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: PlanArtista


# Salida


class PerfilPublico(BaseModel):
    handle: str
    nombre: str
    bio: str | None
    categorias: list[str]
    provincia: str | None
    es_artista: bool
    verificado: bool

    @classmethod
    def desde(cls, perfil: Profile) -> Self:
        return cls(**_campos_publicos(perfil))


class PerfilPropio(PerfilPublico):
    rol: RolPerfil
    plan: PlanArtista | None
    tarifa_porcentaje: Decimal | None
    onboarding: EstadoOnboarding
    puede_cobrar: bool

    @classmethod
    def desde(cls, perfil: Profile, politicas: PoliticasPedido) -> Self:
        es_artista = perfil.rol == RolPerfil.ARTISTA
        return cls(
            **_campos_publicos(perfil),
            rol=perfil.rol,
            plan=perfil.plan if es_artista else None,
            tarifa_porcentaje=(
                tarifa_para_plan(perfil.plan, politicas) if es_artista else None
            ),
            onboarding=perfil.pasarela_onboarding,
            puede_cobrar=dominio.puede_cobrar(perfil),
        )


class ResultadoPlan(BaseModel):
    plan: PlanArtista
    tarifa_porcentaje: Decimal
    tarifa_sincronizada: bool | None


class EstadoOnboardingRespuesta(BaseModel):
    estado: EstadoOnboarding
    # Solo para el dueno. Puede venir nula al consultar una cuenta existente
    url_onboarding: str | None
    puede_cobrar: bool


def _campos_publicos(perfil: Profile) -> dict:
    return {
        "handle": perfil.handle,
        "nombre": perfil.nombre,
        "bio": perfil.bio,
        "categorias": list(perfil.categorias or []),
        "provincia": perfil.provincia,
        "es_artista": perfil.rol == RolPerfil.ARTISTA,
        "verificado": perfil.is_verified,
    }
