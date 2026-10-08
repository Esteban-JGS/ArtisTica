"""Esquemas del catalogo. Las validaciones de forma llaman al dominio y dan 422.

El titulo y la descripcion rechazan telefonos y WhatsApp igual que el perfil:
el contacto va por la plataforma. El precio solo sale en una obra disponible.
"""

import uuid
from datetime import datetime
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

from src.core.config import settings
from src.domain import catalogo as dominio
from src.domain import perfiles as dominio_perfiles
from src.domain.enums import EstadoObra, PlanArtista, TipoServicio
from src.schemas.medios import ImagenPublica
from src.schemas.perfiles import Categorias
from src.services.catalogo import LimitesArtista, ObraDetalle, ServicioDetalle
from src.storage import Almacenamiento


def _sin_contacto(texto: str) -> str:
    """El mismo rechazo que en el perfil: el contacto va por la plataforma."""
    if dominio_perfiles.contiene_contacto_prohibido(texto):
        raise ValueError(
            "No se permiten telefonos ni WhatsApp: el contacto va por la plataforma"
        )
    return texto


def _precio_valido(precio: Decimal) -> Decimal:
    problema = dominio.problema_de_precio(precio, settings.MONTO_MINIMO_PEDIDO)
    if problema is not None:
        raise ValueError(problema)
    return precio


def _estado_elegible(estado: EstadoObra) -> EstadoObra:
    if not dominio.es_estado_editable(estado):
        raise ValueError(
            "Solo podes poner la obra en exhibicion o disponible: "
            "la venta la marca el pedido"
        )
    return estado


def _dentro_del_maximo(medios: list[uuid.UUID]) -> list[uuid.UUID]:
    maximo = settings.MEDIOS_POR_OBRA_MAXIMO
    if len(medios) > maximo:
        raise ValueError(f"Una obra admite {maximo} imagenes como maximo")
    if len(set(medios)) != len(medios):
        raise ValueError("Hay imagenes repetidas")
    return medios


Titulo = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    AfterValidator(_sin_contacto),
]
Descripcion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=2000),
    AfterValidator(_sin_contacto),
]
Monto = Annotated[Decimal, AfterValidator(_precio_valido)]
EstadoElegible = Annotated[EstadoObra, AfterValidator(_estado_elegible)]
Medios = Annotated[
    list[uuid.UUID], Field(min_length=1), AfterValidator(_dentro_del_maximo)
]


# Entrada


class ObraNueva(BaseModel):
    model_config = ConfigDict(extra="forbid")

    titulo: Titulo
    descripcion: Descripcion | None = None
    categorias: Categorias = Field(default_factory=list)
    estado: EstadoElegible = EstadoObra.EXHIBICION
    # Obligatorio y valido si nace disponible: lo exige el servicio
    precio: Monto | None = None
    medios: Medios


class ObraActualizacion(BaseModel):
    """Solo se aplican los campos presentes en el cuerpo."""

    model_config = ConfigDict(extra="forbid")

    titulo: Titulo | None = None
    descripcion: Descripcion | None = None
    categorias: Categorias | None = None
    estado: EstadoElegible | None = None
    precio: Monto | None = None
    medios: Medios | None = None

    @model_validator(mode="after")
    def _obligatorios_no_nulos(self) -> Self:
        for campo in ("titulo", "categorias", "estado", "medios"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"{campo} no puede ser nulo")
        return self


class ServicioNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    titulo: Titulo
    descripcion: Descripcion | None = None
    precio_base: Monto
    tipo: TipoServicio
    activo: bool = True


class ServicioActualizacion(BaseModel):
    """Solo se aplican los campos presentes en el cuerpo."""

    model_config = ConfigDict(extra="forbid")

    titulo: Titulo | None = None
    descripcion: Descripcion | None = None
    precio_base: Monto | None = None
    tipo: TipoServicio | None = None
    activo: bool | None = None

    @model_validator(mode="after")
    def _obligatorios_no_nulos(self) -> Self:
        for campo in ("titulo", "precio_base", "tipo", "activo"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"{campo} no puede ser nulo")
        return self


# Salida


class ObraRespuesta(BaseModel):
    id: uuid.UUID
    artista_handle: str
    titulo: str
    descripcion: str | None
    estado: EstadoObra
    # Solo en una obra disponible: en exhibicion no se vende y vendida ya no se vende
    precio: Decimal | None
    categorias: list[str]
    medios: list[ImagenPublica]
    created_at: datetime

    @classmethod
    def desde(cls, detalle: ObraDetalle, almacenamiento: Almacenamiento) -> Self:
        obra = detalle.obra
        disponible = obra.estado == EstadoObra.DISPONIBLE
        return cls(
            id=obra.id,
            artista_handle=detalle.artista_handle,
            titulo=obra.titulo,
            descripcion=obra.descripcion,
            estado=obra.estado,
            precio=obra.precio if disponible else None,
            categorias=list(obra.categorias or []),
            medios=[ImagenPublica.desde(m, almacenamiento) for m in detalle.medios],
            created_at=obra.created_at,
        )


class ServicioRespuesta(BaseModel):
    id: uuid.UUID
    artista_handle: str
    titulo: str
    descripcion: str | None
    precio_base: Decimal
    tipo: TipoServicio
    activo: bool

    @classmethod
    def desde(cls, detalle: ServicioDetalle) -> Self:
        servicio = detalle.servicio
        return cls(
            id=servicio.id,
            artista_handle=detalle.artista_handle,
            titulo=servicio.titulo,
            descripcion=servicio.descripcion,
            precio_base=servicio.precio_base,
            tipo=servicio.tipo,
            activo=servicio.activo,
        )


class LimitesRespuesta(BaseModel):
    plan: PlanArtista
    servicios_activos: int
    # Nulo: sin limite
    limite_servicios_activos: int | None
    obras_disponibles: int
    limite_obras_disponibles: int | None

    @classmethod
    def desde(cls, limites: LimitesArtista) -> Self:
        return cls(
            plan=limites.plan,
            servicios_activos=limites.servicios_activos,
            limite_servicios_activos=limites.limite_servicios_activos,
            obras_disponibles=limites.obras_disponibles,
            limite_obras_disponibles=limites.limite_obras_disponibles,
        )
