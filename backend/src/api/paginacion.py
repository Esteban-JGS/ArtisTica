"""Lo de HTTP de la paginacion por cursor: parametros de la consulta y respuesta.

El cursor, el orden y la consulta viven en `src/services/paginacion.py`: aca
solo se leen `cursor` y `tamano`, y un cursor mal formado se traduce a 422.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.core.config import settings
from src.services.paginacion import (
    CursorInvalido,
    ParametrosPagina,
    decodificar_cursor,
)


class Pagina[T](BaseModel):
    items: list[T]
    # Nulo en la ultima pagina
    siguiente_cursor: str | None


def parametros_de_pagina(
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    tamano: Annotated[
        int, Query(ge=1, le=settings.PAGINA_TAMANO_MAXIMO)
    ] = settings.PAGINA_TAMANO_DEFECTO,
) -> ParametrosPagina:
    """Traduce los parametros de la consulta. Un cursor mal formado da 422."""
    try:
        clave = decodificar_cursor(cursor) if cursor else None
    except CursorInvalido as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return ParametrosPagina(tamano=tamano, clave=clave)


Paginacion = Annotated[ParametrosPagina, Depends(parametros_de_pagina)]
