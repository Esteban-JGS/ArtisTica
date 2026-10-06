"""Reglas puras de perfiles."""

from decimal import Decimal

import pytest

from src.core.config import settings
from src.domain.perfiles import (
    contiene_contacto_prohibido,
    normalizar_handle,
    tarifa_fija_de_cuenta,
)
from src.domain.politicas import PoliticasPedido
from src.models import PlanArtista

POLITICAS = PoliticasPedido.desde_config(settings)


def test_05_normalizar_handle():
    assert normalizar_handle("  Ana_Pinta ") == "ana_pinta"
    for invalido in ("ab", "a" * 31, "ana-pinta", "ana pinta", "yo"):
        with pytest.raises(ValueError, match="El handle lleva de 3 a 30 caracteres"):
            normalizar_handle(invalido)


@pytest.mark.parametrize(
    "texto",
    [
        "Llamame al 8888-8888",
        "8888 8888",
        "88888888",
        "+506 8888 8888",
        "Escribime por WhatsApp",
        "https://wa.me/50688888888",
    ],
)
def test_06_detecta_contacto_prohibido(texto):
    assert contiene_contacto_prohibido(texto)


@pytest.mark.parametrize(
    "texto",
    ["instagram.com/ana", "Pinto desde 2026", "encargos desde 25000"],
)
def test_07_sin_falso_positivo(texto):
    assert not contiene_contacto_prohibido(texto)


def test_08_tarifa_fija_de_cuenta():
    estudio = POLITICAS.tarifa_estudio_porcentaje
    taller = POLITICAS.tarifa_taller_porcentaje
    assert tarifa_fija_de_cuenta(PlanArtista.ESTUDIO, [], POLITICAS) == estudio
    # Como vuelven de la base: Numeric(5, 2)
    en_base = estudio.quantize(Decimal("0.01"))
    assert (
        tarifa_fija_de_cuenta(PlanArtista.ESTUDIO, [en_base] * 2, POLITICAS) == estudio
    )
    assert (
        tarifa_fija_de_cuenta(PlanArtista.ESTUDIO, [estudio, taller], POLITICAS) is None
    )
