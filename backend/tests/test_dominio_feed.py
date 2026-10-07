"""Dominio del feed y cursor compuesto. Sin base de datos."""

import base64
import json
import uuid
from datetime import UTC, datetime

import pytest

from src.domain.feed import Origen, cuantos_de_cada, intercalar
from src.services.paginacion import (
    ClaveCursor,
    CursorInvalido,
    EstadoFlujo,
    codificar_cursor,
    codificar_cursor_compuesto,
    decodificar_cursor_compuesto,
)

FLUJOS = frozenset({"general", "nuevo_talento"})


def test_01_cuantos_de_cada():
    assert cuantos_de_cada(20, 5) == (16, 4)
    assert cuantos_de_cada(3, 5) == (3, 0)
    assert cuantos_de_cada(5, 5) == (4, 1)
    with pytest.raises(ValueError, match="cuota"):
        cuantos_de_cada(10, 1)


def test_02_intercalar():
    generales = [f"g{i}" for i in range(8)]
    nuevos = ["n0", "n1"]
    pagina = intercalar(generales, nuevos, 10, 5)
    assert [i.elemento for i in pagina] == [
        "g0", "g1", "g2", "g3", "n0", "g4", "g5", "g6", "g7", "n1",
    ]  # fmt: skip
    # Posiciones 5 y 10, contando desde 1
    assert [p for p, i in enumerate(pagina, 1) if i.origen == Origen.NUEVO_TALENTO] == [
        5,
        10,
    ]

    # Faltan nuevos: los generales completan
    pagina = intercalar([f"g{i}" for i in range(12)], ["n0"], 10, 5)
    assert [i.elemento for i in pagina] == [
        "g0", "g1", "g2", "g3", "n0", "g4", "g5", "g6", "g7", "g8",
    ]  # fmt: skip

    # Faltan generales: los nuevos completan
    pagina = intercalar(["g0", "g1"], [f"n{i}" for i in range(12)], 10, 5)
    assert [i.elemento for i in pagina] == [
        "g0", "g1", "n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7",
    ]  # fmt: skip
    assert all(
        i.origen
        == (Origen.GENERAL if i.elemento.startswith("g") else Origen.NUEVO_TALENTO)
        for i in pagina
    )

    # Nunca se repite, aunque las dos listas juntas no lleguen al tamano
    pagina = intercalar(["g0", "g1"], ["n0"], 10, 5)
    assert sorted(i.elemento for i in pagina) == ["g0", "g1", "n0"]
    assert intercalar([], [], 10, 5) == []


def test_03_cursor_compuesto():
    clave = ClaveCursor(datetime(2026, 10, 7, 12, 30, tzinfo=UTC), uuid.uuid4())
    posiciones = {"general": clave, "nuevo_talento": None}
    cursor = codificar_cursor_compuesto(posiciones)
    assert decodificar_cursor_compuesto(cursor, FLUJOS) == posiciones

    agotado = {"general": EstadoFlujo.AGOTADO, "nuevo_talento": clave}
    assert (
        decodificar_cursor_compuesto(codificar_cursor_compuesto(agotado), FLUJOS)
        == agotado
    )

    simple = codificar_cursor(clave.creado_en, clave.id)
    otros_flujos = codificar_cursor_compuesto({"general": None})
    crudo = {"flujos": {"general": {"t": "2026-10-07T12:30:00", "id": str(clave.id)}}}
    crudo["flujos"]["nuevo_talento"] = None
    sin_zona = base64.urlsafe_b64encode(json.dumps(crudo).encode()).decode()
    for malo in ("no-es-base64!!", "YWJj", cursor[:-4], simple, otros_flujos, sin_zona):
        with pytest.raises(CursorInvalido):
            decodificar_cursor_compuesto(malo, FLUJOS)
    with pytest.raises(TypeError):
        codificar_cursor_compuesto({"general": "no es una posicion"})
