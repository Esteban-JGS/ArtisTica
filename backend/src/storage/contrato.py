"""Contrato del almacenamiento de archivos.

Nada fuera de `src.storage` conoce al proveedor: todo pasa por este contrato.
Las rutas las arma quien llama; el almacenamiento no las inventa ni las valida
contra el dominio.

Quien reintenta un job mira solo `reintentable`. Ningun mensaje lleva secretos.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, kw_only=True)
class SubidaFirmada:
    bucket: str
    ruta: str
    # Sensibles: permiten escribir en el bucket. Nunca a logs.
    token: str = field(repr=False)
    url_subida: str = field(repr=False)
    expira_en: datetime


@dataclass(frozen=True, kw_only=True)
class InfoObjeto:
    tamano_bytes: int
    content_type: str | None


@runtime_checkable
class Almacenamiento(Protocol):
    async def firmar_subida(self, bucket: str, ruta: str) -> SubidaFirmada: ...

    async def info(self, bucket: str, ruta: str) -> InfoObjeto | None:
        """None si el objeto no existe."""
        ...

    async def descargar(self, bucket: str, ruta: str) -> bytes: ...

    async def subir(
        self, bucket: str, ruta: str, contenido: bytes, content_type: str
    ) -> None: ...

    async def borrar(self, bucket: str, rutas: Sequence[str]) -> None: ...

    def url_publica(self, bucket: str, ruta: str) -> str: ...


class ErrorAlmacenamiento(Exception):
    """Base de todo error de la capa de almacenamiento."""

    reintentable: bool = False

    def __init__(self, mensaje: str, *, reintentable: bool | None = None) -> None:
        super().__init__(mensaje)
        if reintentable is not None:
            self.reintentable = reintentable


class AlmacenamientoNoDisponible(ErrorAlmacenamiento):
    """Timeout, 5xx o red."""

    reintentable = True


class CredencialesAlmacenamiento(ErrorAlmacenamiento):
    """401, 403 o falta la clave. Es un error de configuracion."""
