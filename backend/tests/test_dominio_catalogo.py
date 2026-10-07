"""Limites de plan, precios y cursor. Logica pura: sin base ni red."""

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.core.config import settings
from src.domain.catalogo import LimitesPlan, cabe_uno_mas, problema_de_precio
from src.domain.enums import PlanArtista
from src.services.paginacion import (
    CursorInvalido,
    codificar_cursor,
    decodificar_cursor,
)

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
LIMITES = LimitesPlan.desde_config(settings)
MINIMO = settings.MONTO_MINIMO_PEDIDO
# Costa Rica, para probar que el cursor no asume UTC
ZONA_CR = timezone(timedelta(hours=-6))


def test_01_limites_por_plan():
    assert LIMITES.servicios_activos(PlanArtista.TALLER) == 2
    assert LIMITES.obras_disponibles(PlanArtista.TALLER) == 5
    assert LIMITES.servicios_activos(PlanArtista.ESTUDIO) is None
    assert LIMITES.obras_disponibles(PlanArtista.ESTUDIO) is None

    assert cabe_uno_mas(4, 5)
    assert not cabe_uno_mas(5, 5)
    # Sin limite siempre cabe uno mas, incluso por encima del de Taller (D11)
    assert cabe_uno_mas(6, None)

    with pytest.raises(ValueError, match="positivos"):
        LimitesPlan(
            servicios_activos_taller=0, obras_disponibles_taller=5, medios_por_obra=10
        )


def test_02_precio_valido():
    assert problema_de_precio(MINIMO, MINIMO) is None
    assert problema_de_precio(MINIMO + Decimal("1.50"), MINIMO) is None

    assert problema_de_precio(None, MINIMO) is not None
    assert problema_de_precio(Decimal("0"), MINIMO) is not None
    assert problema_de_precio(Decimal("-100.00"), MINIMO) is not None
    assert problema_de_precio(Decimal("9999.999"), MINIMO) is not None
    assert problema_de_precio(MINIMO - Decimal("0.01"), MINIMO) is not None


def test_03_cursor_ida_y_vuelta():
    creado_en = datetime(2026, 10, 1, 12, 30, 45, 123456, tzinfo=UTC)
    id_ = uuid.uuid4()
    clave = decodificar_cursor(codificar_cursor(creado_en, id_))
    assert clave.creado_en == creado_en
    assert clave.creado_en.tzinfo is not None
    assert clave.id == id_

    # Con otra zona se conserva el instante y el desplazamiento
    en_cr = creado_en.astimezone(ZONA_CR)
    devuelta = decodificar_cursor(codificar_cursor(en_cr, id_)).creado_en
    assert devuelta == creado_en
    assert devuelta.utcoffset() == timedelta(hours=-6)

    with pytest.raises(ValueError, match="zona horaria"):
        codificar_cursor(creado_en.replace(tzinfo=None), id_)

    # Lo que el endpoint traduce a 422
    for malo in ("no-es-base64!!", "YWJj", codificar_cursor(creado_en, id_)[:-4]):
        with pytest.raises(CursorInvalido):
            decodificar_cursor(malo)


def test_16_paginacion_sin_fastapi():
    """La capa de servicios no arrastra FastAPI: lo de HTTP vive en src/api."""
    codigo = (
        "import sys\n"
        "import src.services.paginacion, src.services.catalogo\n"
        "cargados = [m for m in sys.modules if m.startswith('fastapi')]\n"
        "assert not cargados, cargados\n"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=RAIZ_BACKEND,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,  # el returncode se revisa en el assert de abajo
    )
    assert resultado.returncode == 0, resultado.stderr
