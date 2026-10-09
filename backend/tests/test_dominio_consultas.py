"""Reglas puras de consultas y chat: aviso de contacto, limites y marcas."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.core.config import Settings
from src.domain.consultas import (
    LimitesConsultas,
    RolEnConsulta,
    marca_siguiente,
    requiere_aviso,
    rol_en_consulta,
)

OBLIGATORIAS = {
    "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/artistica",
    "ALEMBIC_DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/artistica",
    "SUPABASE_URL": "http://supabase.local",
}
AHORA = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def test_7_01_requiere_aviso():
    con_aviso = (
        "pasame al 8888-8888",
        "+506 7000 0000",
        "te hago un SINPE",
        "sinpe movil",
        "escribime al WhatsApp",
    )
    sin_aviso = ("lo entrego en 2026", "mi presupuesto es 50000", "hola")
    assert all(requiere_aviso(t) for t in con_aviso)
    assert not any(requiere_aviso(t) for t in sin_aviso)


def test_7_02_limites_consultas():
    with pytest.raises(ValueError, match="positivos"):
        LimitesConsultas(dias_cuenta_reciente=0, consultas_por_ventana=5)
    with pytest.raises(ValueError, match="positivos"):
        LimitesConsultas(dias_cuenta_reciente=7, consultas_por_ventana=0)

    limites = LimitesConsultas(dias_cuenta_reciente=7, consultas_por_ventana=5)
    assert limites.es_reciente(AHORA - timedelta(days=6, hours=23), AHORA)
    assert not limites.es_reciente(AHORA - timedelta(days=7), AHORA)
    assert limites.cabe_otra(4)
    assert not limites.cabe_otra(5)

    defecto = LimitesConsultas.desde_config(Settings(_env_file=None, **OBLIGATORIAS))
    assert defecto == limites


def test_7_03_marca_siguiente_nunca_retrocede():
    un_micro = timedelta(microseconds=1)
    assert marca_siguiente(None, AHORA) == AHORA
    assert marca_siguiente(AHORA, AHORA) == AHORA + un_micro
    futuro = AHORA + timedelta(seconds=3)
    assert marca_siguiente(futuro, AHORA) == futuro + un_micro
    assert marca_siguiente(AHORA - timedelta(seconds=1), AHORA) == AHORA


def test_7_03_rol_en_consulta():
    cliente, artista, tercero = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert rol_en_consulta(cliente, artista, cliente) is RolEnConsulta.CLIENTE
    assert rol_en_consulta(cliente, artista, artista) is RolEnConsulta.ARTISTA
    assert rol_en_consulta(cliente, artista, tercero) is None


@pytest.mark.parametrize(
    "variable", ["DIAS_CUENTA_RECIENTE", "CONSULTAS_POR_DIA_CUENTA_RECIENTE"]
)
def test_7_04_settings_rechaza_limites_en_cero(variable):
    with pytest.raises(ValidationError, match=variable):
        Settings(_env_file=None, **OBLIGATORIAS, **{variable: 0})
