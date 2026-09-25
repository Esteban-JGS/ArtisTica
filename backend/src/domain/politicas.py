from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import Settings

CERO = Decimal("0")
CIEN = Decimal("100")


@dataclass(frozen=True)
class PoliticasPedido:
    """Politicas del negocio (D5). Sin valores por defecto: esos viven en Settings."""

    anticipo_porcentaje_minimo: Decimal
    anticipo_porcentaje_maximo: Decimal
    anticipo_porcentaje_defecto: Decimal
    ventana_disputa: timedelta
    cancelacion_evento_total: timedelta
    cancelacion_evento_parcial: timedelta
    cancelacion_evento_porcentaje_parcial: Decimal
    monto_minimo_pedido: Decimal
    tarifa_taller_porcentaje: Decimal
    tarifa_estudio_porcentaje: Decimal

    def __post_init__(self) -> None:
        minimo = self.anticipo_porcentaje_minimo
        maximo = self.anticipo_porcentaje_maximo
        if not CERO < minimo <= self.anticipo_porcentaje_defecto <= maximo < CIEN:
            raise ValueError(
                "El anticipo debe cumplir 0 < minimo <= defecto <= maximo < 100"
            )
        if self.ventana_disputa <= timedelta(0):
            raise ValueError("La ventana de disputa debe ser positiva")
        if not timedelta(0) <= self.cancelacion_evento_parcial:
            raise ValueError("El plazo de cancelacion parcial no puede ser negativo")
        if self.cancelacion_evento_parcial > self.cancelacion_evento_total:
            raise ValueError("El plazo parcial no puede superar al total")
        if not CERO <= self.cancelacion_evento_porcentaje_parcial <= CIEN:
            raise ValueError("El reembolso parcial debe estar entre 0 y 100")
        if self.monto_minimo_pedido <= CERO:
            raise ValueError("El monto minimo debe ser positivo")
        for tarifa in (self.tarifa_taller_porcentaje, self.tarifa_estudio_porcentaje):
            if not CERO <= tarifa < CIEN:
                raise ValueError("La tarifa debe estar entre 0 y 100")

    @classmethod
    def desde_config(cls, config: Settings) -> PoliticasPedido:
        return cls(
            anticipo_porcentaje_minimo=config.ANTICIPO_PORCENTAJE_MINIMO,
            anticipo_porcentaje_maximo=config.ANTICIPO_PORCENTAJE_MAXIMO,
            anticipo_porcentaje_defecto=config.ANTICIPO_PORCENTAJE_DEFECTO,
            ventana_disputa=timedelta(days=config.DIAS_VENTANA_DISPUTA),
            cancelacion_evento_total=timedelta(
                days=config.CANCELACION_EVENTO_DIAS_TOTAL
            ),
            cancelacion_evento_parcial=timedelta(
                days=config.CANCELACION_EVENTO_DIAS_PARCIAL
            ),
            cancelacion_evento_porcentaje_parcial=(
                config.CANCELACION_EVENTO_PORCENTAJE_PARCIAL
            ),
            monto_minimo_pedido=config.MONTO_MINIMO_PEDIDO,
            tarifa_taller_porcentaje=config.TARIFA_TALLER_PORCENTAJE,
            tarifa_estudio_porcentaje=config.TARIFA_ESTUDIO_PORCENTAJE,
        )
