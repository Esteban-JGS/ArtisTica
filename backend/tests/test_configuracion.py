"""Reglas de la configuracion al cargar. Nunca toca el settings global."""

import pytest
import sentry_sdk
from pydantic import ValidationError

from src.core.config import Settings
from src.core.sentry import configurar_sentry

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


def _llamadas_a_init(monkeypatch) -> list[dict]:
    llamadas: list[dict] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: llamadas.append(kw))
    return llamadas


def test_6d_01_sin_dsn_sentry_no_arranca(monkeypatch):
    llamadas = _llamadas_a_init(monkeypatch)
    assert configurar_sentry(_settings(SENTRY_DSN=None)) is False
    assert llamadas == []


def test_6d_02_con_dsn_sentry_arranca_sin_datos_sensibles(monkeypatch):
    llamadas = _llamadas_a_init(monkeypatch)
    config = _settings(
        SENTRY_DSN="https://clave@sentry.local/1", SENTRY_TRACES_SAMPLE_RATE=0.25
    )
    assert configurar_sentry(config) is True
    assert len(llamadas) == 1
    assert llamadas[0]["send_default_pii"] is False
    assert llamadas[0]["include_local_variables"] is False
    assert llamadas[0]["traces_sample_rate"] == 0.25
    assert llamadas[0]["dsn"] == "https://clave@sentry.local/1"


def test_6d_03_muestreo_de_trazas_fuera_de_rango_no_carga():
    for valor in (-0.1, 1.5):
        assert "SENTRY_TRACES_SAMPLE_RATE" in _falla(SENTRY_TRACES_SAMPLE_RATE=valor)
    assert _settings().SENTRY_TRACES_SAMPLE_RATE == 0.1
