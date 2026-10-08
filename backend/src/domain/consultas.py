"""Reglas de consultas y chat. Logica pura: recibe valores y devuelve valores.

No conoce la base ni el reloj. En el chat un dato de contacto no se rechaza:
el mensaje se guarda con un aviso que ven los dos lados.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.domain.perfiles import contiene_contacto_prohibido

if TYPE_CHECKING:
    from src.core.config import Settings

AVISO_PAGO_FUERA = "Si pagás fuera de ArtísTica, no tenés protección ni reseña"
# Ventana del limite de consultas para cuentas nuevas
VENTANA_LIMITE = timedelta(hours=24)

_UN_MICROSEGUNDO = timedelta(microseconds=1)


class RolEnConsulta(enum.StrEnum):
    CLIENTE = "cliente"
    ARTISTA = "artista"


def requiere_aviso(texto: str) -> bool:
    """Telefono, WhatsApp o SINPE: pagar por fuera deja sin proteccion."""
    return contiene_contacto_prohibido(texto) or "sinpe" in texto.casefold()


@dataclass(frozen=True)
class LimitesConsultas:
    """Cuantas consultas abre una cuenta nueva por ventana."""

    dias_cuenta_reciente: int
    consultas_por_ventana: int

    def __post_init__(self) -> None:
        if self.dias_cuenta_reciente < 1 or self.consultas_por_ventana < 1:
            raise ValueError("Los limites de consultas tienen que ser positivos")

    @classmethod
    def desde_config(cls, config: Settings) -> LimitesConsultas:
        return cls(
            dias_cuenta_reciente=config.DIAS_CUENTA_RECIENTE,
            consultas_por_ventana=config.CONSULTAS_POR_DIA_CUENTA_RECIENTE,
        )

    def es_reciente(self, perfil_creado: datetime, ahora: datetime) -> bool:
        """Con exactamente `dias_cuenta_reciente` dias ya no es reciente."""
        return ahora - perfil_creado < timedelta(days=self.dias_cuenta_reciente)

    def cabe_otra(self, abiertas_en_ventana: int) -> bool:
        return abiertas_en_ventana < self.consultas_por_ventana


def marca_siguiente(ultimo: datetime | None, ahora: datetime) -> datetime:
    """La marca del mensaje nuevo. Nunca retrocede respecto del anterior."""
    if ultimo is None:
        return ahora
    return max(ahora, ultimo + _UN_MICROSEGUNDO)


def rol_en_consulta(
    cliente_id: uuid.UUID, artista_id: uuid.UUID, usuario_id: uuid.UUID
) -> RolEnConsulta | None:
    """None si el usuario no participa."""
    if usuario_id == cliente_id:
        return RolEnConsulta.CLIENTE
    if usuario_id == artista_id:
        return RolEnConsulta.ARTISTA
    return None
