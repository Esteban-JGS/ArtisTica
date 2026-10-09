"""Almacenamiento falso, en memoria.

Lo usan las pruebas y la demo. Guarda los objetos por (bucket, ruta), exige
una firma previa para subir como lo haria la URL firmada, y puede fallar a
pedido con `programar_falla`.
"""

import secrets
from collections import defaultdict, deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.storage.contrato import (
    DescargaFirmada,
    ErrorAlmacenamiento,
    InfoObjeto,
    SubidaFirmada,
)

URL_BASE = "https://almacenamiento-falso.invalid"
VIGENCIA_SUBIDA_FIRMADA = timedelta(hours=2)

OPERACIONES = frozenset(
    {"firmar_subida", "info", "descargar", "subir", "borrar", "firmar_descarga"}
)


def _reloj_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class _Objeto:
    contenido: bytes
    content_type: str


class AlmacenamientoFalso:
    def __init__(self, *, reloj: Callable[[], datetime] = _reloj_utc) -> None:
        self._reloj = reloj
        self._objetos: dict[tuple[str, str], _Objeto] = {}
        self._firmas: dict[tuple[str, str], datetime] = {}
        self._fallas: defaultdict[str, deque[ErrorAlmacenamiento]] = defaultdict(deque)

    def __repr__(self) -> str:
        return f"AlmacenamientoFalso(objetos={len(self._objetos)})"

    # Controles del falso

    def programar_falla(self, operacion: str, error: ErrorAlmacenamiento) -> None:
        """La proxima llamada a `operacion` levanta `error`."""
        if operacion not in OPERACIONES:
            raise ValueError(f"Operacion desconocida: {operacion}")
        if not isinstance(error, ErrorAlmacenamiento):
            raise TypeError("La falla tiene que ser un ErrorAlmacenamiento")
        self._fallas[operacion].append(error)

    def simular_subida(
        self, bucket: str, ruta: str, contenido: bytes, content_type: str
    ) -> None:
        """Lo que hace el cliente con la URL firmada."""
        vence = self._firmas.get((bucket, ruta))
        if vence is None:
            raise ValueError(f"No hay una subida firmada para {bucket}/{ruta}")
        if vence <= self._reloj():
            raise ValueError(f"La subida firmada para {bucket}/{ruta} vencio")
        self._objetos[(bucket, ruta)] = _Objeto(bytes(contenido), content_type)

    def existe(self, bucket: str, ruta: str) -> bool:
        return (bucket, ruta) in self._objetos

    def limpiar(self) -> None:
        self._objetos.clear()
        self._firmas.clear()
        self._fallas.clear()

    # Contrato

    async def firmar_subida(self, bucket: str, ruta: str) -> SubidaFirmada:
        self._fallar_si_programado("firmar_subida")
        token = secrets.token_urlsafe(24)
        expira_en = self._reloj() + VIGENCIA_SUBIDA_FIRMADA
        self._firmas[(bucket, ruta)] = expira_en
        return SubidaFirmada(
            bucket=bucket,
            ruta=ruta,
            token=token,
            url_subida=f"{URL_BASE}/subir/{bucket}/{ruta}?token={token}",
            expira_en=expira_en,
        )

    async def info(self, bucket: str, ruta: str) -> InfoObjeto | None:
        self._fallar_si_programado("info")
        objeto = self._objetos.get((bucket, ruta))
        if objeto is None:
            return None
        return InfoObjeto(
            tamano_bytes=len(objeto.contenido), content_type=objeto.content_type
        )

    async def descargar(self, bucket: str, ruta: str) -> bytes:
        self._fallar_si_programado("descargar")
        objeto = self._objetos.get((bucket, ruta))
        if objeto is None:
            raise ErrorAlmacenamiento(f"El objeto {bucket}/{ruta} no existe")
        return objeto.contenido

    async def subir(
        self, bucket: str, ruta: str, contenido: bytes, content_type: str
    ) -> None:
        self._fallar_si_programado("subir")
        self._objetos[(bucket, ruta)] = _Objeto(bytes(contenido), content_type)

    async def borrar(self, bucket: str, rutas: Sequence[str]) -> None:
        self._fallar_si_programado("borrar")
        for ruta in rutas:
            self._objetos.pop((bucket, ruta), None)

    def url_publica(self, bucket: str, ruta: str) -> str:
        return f"{URL_BASE}/{bucket}/{ruta}"

    async def firmar_descarga(
        self, bucket: str, ruta: str, *, segundos: int
    ) -> DescargaFirmada:
        if segundos <= 0:
            raise ValueError("La descarga firmada necesita segundos positivos")
        self._fallar_si_programado("firmar_descarga")
        if (bucket, ruta) not in self._objetos:
            raise ErrorAlmacenamiento(f"El objeto {bucket}/{ruta} no existe")
        expira_en = self._reloj() + timedelta(seconds=segundos)
        return DescargaFirmada(
            url=f"{URL_BASE}/firmada/{bucket}/{ruta}?expira={int(expira_en.timestamp())}",
            expira_en=expira_en,
        )

    def _fallar_si_programado(self, operacion: str) -> None:
        if self._fallas[operacion]:
            raise self._fallas[operacion].popleft()
