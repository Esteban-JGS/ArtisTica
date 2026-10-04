"""Reglas de la configuracion al cargar. Nunca toca el settings global."""

import pytest
from pydantic import ValidationError

from src.core.config import Settings

OBLIGATORIAS = {
    "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/artistica",
    "ALEMBIC_DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/artistica",
    "SUPABASE_URL": "http://supabase.local",
}
REALES = {"PASARELA": "onvo", "ALMACENAMIENTO": "supabase"}


def _settings(**valores) -> Settings:
    # _env_file=None: no lee el .env local
    return Settings(_env_file=None, **OBLIGATORIAS, **valores)


def _falla(**valores) -> str:
    with pytest.raises(ValidationError) as exc:
        _settings(**valores)
    return str(exc.value)


def test_01_defectos_en_dev_cargan():
    s = _settings(ENVIRONMENT="dev")
    assert s.WORKERS == 1
    assert s.ESTUDIO_AUTOSERVICIO is True


def test_02_produccion_rechaza_pasarela_falsa():
    for valor in ("falsa", " Falsa "):
        mensaje = _falla(
            ENVIRONMENT="production",
            PASARELA=valor,
            ALMACENAMIENTO="supabase",
            ESTUDIO_AUTOSERVICIO=False,
        )
        assert "PASARELA" in mensaje


def test_03_produccion_rechaza_almacenamiento_falso():
    mensaje = _falla(
        ENVIRONMENT="prod",
        PASARELA="onvo",
        ALMACENAMIENTO="falso",
        ESTUDIO_AUTOSERVICIO=False,
    )
    assert "ALMACENAMIENTO" in mensaje


def test_04_produccion_exige_estudio_sin_autoservicio():
    mensaje = _falla(ENVIRONMENT="production", ESTUDIO_AUTOSERVICIO=True, **REALES)
    assert "ESTUDIO_AUTOSERVICIO" in mensaje

    s = _settings(ENVIRONMENT="production", ESTUDIO_AUTOSERVICIO=False, **REALES)
    assert s.ESTUDIO_AUTOSERVICIO is False


def test_05_varios_workers_solo_sin_adaptadores_falsos():
    for falsos in ({"PASARELA": "falsa"}, {"ALMACENAMIENTO": "falso"}):
        valores = {**REALES, **falsos}
        assert "WORKERS" in _falla(WORKERS=2, **valores)

    assert _settings(WORKERS=2, **REALES).WORKERS == 2
    assert "WORKERS" in _falla(WORKERS=0)


def test_06_demo_con_adaptadores_falsos_carga():
    s = _settings(
        ENVIRONMENT="demo",
        PASARELA="falsa",
        ALMACENAMIENTO="falso",
        WORKERS=1,
        ESTUDIO_AUTOSERVICIO=True,
    )
    assert s.ENVIRONMENT == "demo"
