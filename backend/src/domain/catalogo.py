"""Limites de plan y precios del catalogo. Logica pura: recibe valores y devuelve valores.

No conoce la base, el almacenamiento ni el reloj. Los valores por defecto viven
en Settings; aca solo se decide con los que llegan.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from src.domain.enums import EstadoObra, PlanArtista

if TYPE_CHECKING:
    from src.core.config import Settings

CENTIMO = Decimal("0.01")
CERO = Decimal("0")

# Los dos estados que el artista elige. A vendida solo la lleva el servicio de pedidos.
ESTADOS_EDITABLES = frozenset({EstadoObra.EXHIBICION, EstadoObra.DISPONIBLE})

# Campos de la ficha: se pueden editar incluso con un pedido en curso
CAMPOS_DE_FICHA = frozenset({"titulo", "descripcion", "categorias"})

MOTIVO_SIN_PRECIO = "Una obra disponible necesita precio"
MOTIVO_NO_POSITIVO = "El precio tiene que ser positivo"
MOTIVO_DEMASIADOS_DECIMALES = "El precio admite dos decimales como maximo"


@dataclass(frozen=True)
class LimitesPlan:
    """Cuanto puede tener activo un artista segun su plan."""

    servicios_activos_taller: int
    obras_disponibles_taller: int
    medios_por_obra: int

    def __post_init__(self) -> None:
        campos = (
            self.servicios_activos_taller,
            self.obras_disponibles_taller,
            self.medios_por_obra,
        )
        if any(valor < 1 for valor in campos):
            raise ValueError("Los limites del catalogo tienen que ser positivos")

    @classmethod
    def desde_config(cls, config: Settings) -> LimitesPlan:
        return cls(
            servicios_activos_taller=config.LIMITE_SERVICIOS_TALLER,
            obras_disponibles_taller=config.LIMITE_OBRAS_DISPONIBLES_TALLER,
            medios_por_obra=config.MEDIOS_POR_OBRA_MAXIMO,
        )

    def servicios_activos(self, plan: PlanArtista) -> int | None:
        """None: sin limite."""
        return self.servicios_activos_taller if plan == PlanArtista.TALLER else None

    def obras_disponibles(self, plan: PlanArtista) -> int | None:
        """None: sin limite. Nunca se limita la galeria en exhibicion."""
        return self.obras_disponibles_taller if plan == PlanArtista.TALLER else None


def cabe_uno_mas(actuales: int, limite: int | None) -> bool:
    """Si se puede sumar uno. D11: con mas de los permitidos no se oculta nada,
    solo no se deja agregar otro."""
    return limite is None or actuales < limite


def problema_de_precio(precio: Decimal | None, minimo: Decimal) -> str | None:
    """Motivo por el que el precio no sirve para una obra disponible o un
    servicio, o None si sirve."""
    if precio is None:
        return MOTIVO_SIN_PRECIO
    if precio <= CERO:
        return MOTIVO_NO_POSITIVO
    if precio != precio.quantize(CENTIMO):
        return MOTIVO_DEMASIADOS_DECIMALES
    if precio < minimo:
        return f"El precio no puede ser menor que {minimo}"
    return None


def es_estado_editable(estado: EstadoObra) -> bool:
    return estado in ESTADOS_EDITABLES


def campos_restringidos(cambios: Iterable[str]) -> frozenset[str]:
    """Los campos del cambio que no son de la ficha: precio, estado y medios."""
    return frozenset(cambios) - CAMPOS_DE_FICHA
