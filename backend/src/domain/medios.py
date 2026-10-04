"""Reglas puras de los medios: tipos permitidos, rutas y validacion de la subida.

Sin base ni almacenamiento.
"""

import uuid
from typing import Protocol

# En el MVP solo hay imagenes. Tipo declarado a extension del objeto.
TIPOS_PERMITIDOS: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
TIPO_IMAGEN = "imagen"

MOTIVO_NO_SUBIDO = "El archivo no se subio"
MOTIVO_DEMASIADO_GRANDE = "El archivo supera el tamano permitido"
MOTIVO_TIPO_DISTINTO = "El tipo del archivo no coincide con el declarado"


class DatosObjeto(Protocol):
    """Lo que el dominio necesita saber del objeto guardado."""

    @property
    def tamano_bytes(self) -> int: ...

    @property
    def content_type(self) -> str | None: ...


def _normalizar_tipo(content_type: str | None) -> str | None:
    if content_type is None:
        return None
    return content_type.split(";", 1)[0].strip().lower() or None


def ruta_para(propietario_id: uuid.UUID, medio_id: uuid.UUID, content_type: str) -> str:
    """La ruta la arma siempre el servidor: `{propietario}/{medio}.{extension}`."""
    extension = TIPOS_PERMITIDOS.get(_normalizar_tipo(content_type) or "")
    if extension is None:
        raise ValueError(f"Tipo de archivo no permitido: {content_type}")
    return f"{propietario_id}/{medio_id}.{extension}"


def problema_de_subida(
    content_type_declarado: str | None, info: DatosObjeto | None, maximo: int
) -> str | None:
    """None si la subida es valida; si no, el motivo."""
    if info is None or info.tamano_bytes <= 0:
        return MOTIVO_NO_SUBIDO
    if info.tamano_bytes > maximo:
        return MOTIVO_DEMASIADO_GRANDE
    declarado = _normalizar_tipo(content_type_declarado)
    if declarado is None or _normalizar_tipo(info.content_type) != declarado:
        return MOTIVO_TIPO_DISTINTO
    return None
