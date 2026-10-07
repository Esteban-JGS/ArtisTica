"""Paginacion por cursor sobre la base, para el catalogo y para el feed.

Orden fijo `created_at DESC, id DESC`. El cursor es opaco: base64 url-safe del
par (fecha, id) de la ultima fila entregada. Nunca se pagina con OFFSET, que
repite y saltea filas cuando se inserta mientras se recorre.

Sin HTTP: `src/api/paginacion.py` lee los parametros de la consulta y traduce
`CursorInvalido` a 422.
"""

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

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


def codificar_cursor(creado_en: datetime, id_: uuid.UUID) -> str:
    if creado_en.tzinfo is None:
        raise ValueError("La fecha del cursor tiene que tener zona horaria")
    crudo = json.dumps({"t": creado_en.isoformat(), "id": str(id_)}).encode()
    return base64.urlsafe_b64encode(crudo).decode().rstrip("=")


def decodificar_cursor(valor: str) -> ClaveCursor:
    relleno = "=" * (-len(valor) % 4)
    try:
        datos = json.loads(base64.urlsafe_b64decode(valor + relleno))
        clave = ClaveCursor(
            creado_en=datetime.fromisoformat(datos["t"]), id=uuid.UUID(datos["id"])
        )
    except (
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        KeyError,
        ValueError,
    ) as exc:
        raise CursorInvalido("El cursor no es valido") from exc
    if clave.creado_en.tzinfo is None:
        raise CursorInvalido("El cursor no trae zona horaria")
    return clave


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
