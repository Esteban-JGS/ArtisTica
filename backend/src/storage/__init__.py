"""Capa de almacenamiento. Se usa a traves del contrato y de `obtener_almacenamiento`.

Unico punto donde se elige el proveedor. El resto del backend usa el contrato.
"""

import functools

from src.core.config import settings
from src.storage.contrato import (
    Almacenamiento,
    AlmacenamientoNoDisponible,
    CredencialesAlmacenamiento,
    ErrorAlmacenamiento,
    InfoObjeto,
    SubidaFirmada,
)
from src.storage.falso import AlmacenamientoFalso

ALMACENAMIENTOS = ("falso", "supabase")
ENTORNOS_PRODUCCION = frozenset({"production", "prod"})


def construir_almacenamiento(nombre: str) -> Almacenamiento:
    """Construye el almacenamiento indicado. Falla con un mensaje claro si falta algo."""
    normalizado = nombre.strip().lower()
    if normalizado == "falso":
        if settings.ENVIRONMENT.strip().lower() in ENTORNOS_PRODUCCION:
            raise ValueError(
                "ALMACENAMIENTO=falso no se permite en produccion: las imagenes "
                "no se guardan en memoria"
            )
        return AlmacenamientoFalso()
    if normalizado == "supabase":
        # Import diferido: `python -m src.storage.supabase` no lo carga dos veces
        from src.storage.supabase import desde_config

        return desde_config(settings)
    raise ValueError(
        f"ALMACENAMIENTO desconocido: {nombre!r}. "
        f"Valores validos: {', '.join(ALMACENAMIENTOS)}"
    )


@functools.cache
def obtener_almacenamiento() -> Almacenamiento:
    """Una instancia por proceso, para que el falso conserve su estado."""
    return construir_almacenamiento(settings.ALMACENAMIENTO)


__all__ = [
    "ALMACENAMIENTOS",
    "Almacenamiento",
    "AlmacenamientoFalso",
    "AlmacenamientoNoDisponible",
    "CredencialesAlmacenamiento",
    "ErrorAlmacenamiento",
    "InfoObjeto",
    "SubidaFirmada",
    "construir_almacenamiento",
    "obtener_almacenamiento",
]
