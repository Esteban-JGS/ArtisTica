"""Armado de una pagina de Explorar. Logica pura: recibe listas y devuelve listas.

Explorar intercala dos flujos ya ordenados por fecha: el general y el de nuevos
talentos. Una de cada `cada_n` posiciones es de un nuevo talento. Nunca entra
una senal de popularidad: el orden dentro de cada flujo es solo cronologico.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum


class Origen(StrEnum):
    GENERAL = "general"
    NUEVO_TALENTO = "nuevo_talento"


# Marca de lista agotada: un elemento puede ser cualquier valor, incluso None
_FIN = object()


@dataclass(frozen=True)
class Intercalado[T]:
    elemento: T
    origen: Origen


def cuantos_de_cada(tamano: int, cada_n: int) -> tuple[int, int]:
    """Cuantos generales y cuantos nuevos talentos lleva una pagina llena."""
    if tamano < 0:
        raise ValueError("El tamano de la pagina no puede ser negativo")
    if cada_n < 2:
        raise ValueError("La cuota tiene que ser de una cada dos o menos")
    nuevos = tamano // cada_n
    return tamano - nuevos, nuevos


def intercalar[T](
    generales: Sequence[T], nuevos: Sequence[T], tamano: int, cada_n: int
) -> list[Intercalado[T]]:
    """Un nuevo talento en cada posicion multiplo de `cada_n`, contando desde 1.

    Si una lista se queda corta, la otra completa los huecos. Cada elemento sale
    una sola vez y cada lista conserva su orden.
    """
    cuantos_de_cada(tamano, cada_n)  # valida los argumentos
    pendientes = {
        Origen.GENERAL: iter(generales),
        Origen.NUEVO_TALENTO: iter(nuevos),
    }
    pagina: list[Intercalado[T]] = []
    for posicion in range(1, tamano + 1):
        preferido = Origen.NUEVO_TALENTO if posicion % cada_n == 0 else Origen.GENERAL
        alterno = (
            Origen.GENERAL
            if preferido == Origen.NUEVO_TALENTO
            else Origen.NUEVO_TALENTO
        )
        siguiente = _tomar(pendientes, preferido) or _tomar(pendientes, alterno)
        if siguiente is None:
            break
        pagina.append(siguiente)
    return pagina


def _tomar[T](
    pendientes: dict[Origen, Iterator[T]], origen: Origen
) -> Intercalado[T] | None:
    elemento = next(pendientes[origen], _FIN)
    if elemento is _FIN:
        return None
    return Intercalado(elemento, origen)
