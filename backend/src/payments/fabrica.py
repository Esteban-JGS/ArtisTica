"""Unico punto donde se elige la pasarela. El resto del backend usa el contrato."""

import functools

from src.core.config import settings
from src.payments.config import ConfigOnvo
from src.payments.contrato import PasarelaDePagos
from src.payments.errores import CredencialesInvalidas
from src.payments.falsa import PasarelaFalsa
from src.payments.onvo import PasarelaOnvo

PASARELAS = ("falsa", "onvo")


def construir_pasarela(
    nombre: str, *, config_onvo: ConfigOnvo | None = None
) -> PasarelaDePagos:
    """Construye la pasarela indicada. Falla con un mensaje claro si falta algo."""
    normalizado = nombre.strip().lower()
    if normalizado == "falsa":
        return PasarelaFalsa()
    if normalizado == "onvo":
        config = config_onvo if config_onvo is not None else ConfigOnvo()
        if config.API_KEY is None or not config.API_KEY.get_secret_value().strip():
            raise CredencialesInvalidas("PASARELA=onvo necesita ONVO_API_KEY")
        return PasarelaOnvo(config)
    raise ValueError(
        f"PASARELA desconocida: {nombre!r}. Valores validos: {', '.join(PASARELAS)}"
    )


@functools.cache
def obtener_pasarela() -> PasarelaDePagos:
    """Una instancia por proceso, para que la falsa conserve su estado."""
    return construir_pasarela(settings.PASARELA)
