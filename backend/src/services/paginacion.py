"""Paginacion por cursor sobre la base, para el catalogo y para el feed.

Orden fijo `created_at DESC, id DESC`. El cursor es opaco: base64 url-safe del
par (fecha, id) de la ultima fila entregada. Nunca se pagina con OFFSET, que
repite y saltea filas cuando se inserta mientras se recorre.

El cursor compuesto lleva la posicion de varios flujos a la vez, como los dos
de Explorar. Cada flujo esta sin empezar (None), en una fila, o agotado.

Sin HTTP: `src/api/paginacion.py` lee los parametros de la consulta y traduce
`CursorInvalido` a 422.
"""

import base64
import binascii
import enum
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import Select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped


class CursorInvalido(Exception):
    """El cursor no es un cursor de esta API. La capa de API lo traduce a 422."""


@dataclass(frozen=True)
class ClaveCursor:
    """La ultima fila entregada. La pagina siguiente empieza despues de ella."""

    creado_en: datetime
    id: uuid.UUID


@dataclass(frozen=True)
class ParametrosPagina:
    tamano: int
    clave: ClaveCursor | None


class EstadoFlujo(enum.Enum):
    AGOTADO = "agotado"


# Donde va un flujo del cursor compuesto: None si no empezo
PosicionFlujo = ClaveCursor | EstadoFlujo | None

# Lo que puede fallar al leer un cursor que no salio de esta API
_ERRORES_DE_LECTURA = (
    binascii.Error,
    UnicodeDecodeError,
    json.JSONDecodeError,
    TypeError,
    KeyError,
    ValueError,
    AttributeError,
)


def _a_json(creado_en: datetime, id_: uuid.UUID) -> dict[str, str]:
    if creado_en.tzinfo is None:
        raise ValueError("La fecha del cursor tiene que tener zona horaria")
    return {"t": creado_en.isoformat(), "id": str(id_)}


def _desde_json(datos: Any) -> ClaveCursor:
    clave = ClaveCursor(
        creado_en=datetime.fromisoformat(datos["t"]), id=uuid.UUID(datos["id"])
    )
    if clave.creado_en.tzinfo is None:
        raise CursorInvalido("El cursor no trae zona horaria")
    return clave


def _opaco(datos: object) -> str:
    crudo = json.dumps(datos).encode()
    return base64.urlsafe_b64encode(crudo).decode().rstrip("=")


def _leer(valor: str) -> Any:
    relleno = "=" * (-len(valor) % 4)
    return json.loads(base64.urlsafe_b64decode(valor + relleno))


def codificar_cursor(creado_en: datetime, id_: uuid.UUID) -> str:
    return _opaco(_a_json(creado_en, id_))


def decodificar_cursor(valor: str) -> ClaveCursor:
    try:
        return _desde_json(_leer(valor))
    except _ERRORES_DE_LECTURA as exc:
        raise CursorInvalido("El cursor no es valido") from exc


def codificar_cursor_compuesto(posiciones: Mapping[str, PosicionFlujo]) -> str:
    """Un cursor con la posicion de cada flujo, por nombre."""
    datos: dict[str, object] = {}
    for flujo, posicion in posiciones.items():
        if isinstance(posicion, ClaveCursor):
            datos[flujo] = _a_json(posicion.creado_en, posicion.id)
        elif posicion is EstadoFlujo.AGOTADO:
            datos[flujo] = EstadoFlujo.AGOTADO.value
        elif posicion is None:
            datos[flujo] = None
        else:
            raise TypeError(f"Posicion de flujo desconocida: {posicion!r}")
    return _opaco({"flujos": datos})


def decodificar_cursor_compuesto(
    valor: str, flujos: frozenset[str]
) -> dict[str, PosicionFlujo]:
    """Inverso de `codificar_cursor_compuesto`. Exige exactamente esos flujos."""
    try:
        datos = _leer(valor)["flujos"]
        if set(datos) != flujos:
            raise CursorInvalido("El cursor no es de este listado")
        return {flujo: _posicion_desde_json(datos[flujo]) for flujo in flujos}
    except _ERRORES_DE_LECTURA as exc:
        raise CursorInvalido("El cursor no es valido") from exc


def _posicion_desde_json(datos: Any) -> PosicionFlujo:
    if datos is None:
        return None
    if datos == EstadoFlujo.AGOTADO.value:
        return EstadoFlujo.AGOTADO
    return _desde_json(datos)


class ConClaveDeOrden(Protocol):
    """Lo que necesita una tabla para paginarse: fecha de creacion e id."""

    created_at: Mapped[datetime]
    id: Mapped[uuid.UUID]


async def traer_pagina[M: ConClaveDeOrden](
    session: AsyncSession,
    stmt: Select[tuple[M]],
    modelo: type[M],
    parametros: ParametrosPagina,
) -> tuple[list[M], str | None]:
    """Las filas de la pagina y el cursor de la siguiente, o None si es la ultima.

    Se piden `tamano + 1` filas: la sobrante solo dice que hay pagina siguiente.
    """
    if parametros.clave is not None:
        stmt = stmt.where(
            tuple_(modelo.created_at, modelo.id)
            < tuple_(parametros.clave.creado_en, parametros.clave.id)
        )
    stmt = stmt.order_by(modelo.created_at.desc(), modelo.id.desc()).limit(
        parametros.tamano + 1
    )
    filas = list((await session.execute(stmt)).scalars())
    if len(filas) <= parametros.tamano:
        return filas, None
    pagina = filas[: parametros.tamano]
    ultima = pagina[-1]
    return pagina, codificar_cursor(ultima.created_at, ultima.id)
