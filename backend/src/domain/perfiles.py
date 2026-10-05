"""Reglas de perfiles, roles y planes. Logica pura: no conoce la base ni la pasarela."""

import re
from collections.abc import Iterable
from decimal import Decimal
from typing import Protocol

from src.domain.enums import EstadoOnboarding, PlanArtista, RolPerfil
from src.domain.pedidos import tarifa_para_plan
from src.domain.politicas import PoliticasPedido

PROVINCIAS = (
    "San José",
    "Alajuela",
    "Cartago",
    "Heredia",
    "Guanacaste",
    "Puntarenas",
    "Limón",
)

HANDLES_RESERVADOS = frozenset({"yo", "admin", "artistica", "soporte", "api"})

_PATRON_HANDLE = re.compile(r"^[a-z0-9_]{3,30}$")

# Ocho digitos que empiezan en 2, 4, 5, 6, 7 u 8, con un separador opcional
# despues del cuarto y prefijo opcional. Sin digitos pegados a los lados, para
# que un año o un monto no cuenten.
_PATRON_TELEFONO = re.compile(
    r"(?<!\d)(?:\+?506[\s.-]?)?[245678]\d{3}[\s.-]?\d{4}(?!\d)"
)
_PATRON_WHATSAPP = re.compile(r"whatsapp|wa\.me", re.IGNORECASE)


def normalizar_handle(texto: str) -> str:
    handle = texto.strip().lower()
    if not _PATRON_HANDLE.fullmatch(handle):
        raise ValueError(
            "El handle lleva de 3 a 30 caracteres: letras sin tilde, numeros o _"
        )
    if handle in HANDLES_RESERVADOS:
        raise ValueError(f"El handle {handle!r} esta reservado")
    return handle


def contiene_contacto_prohibido(texto: str) -> bool:
    """Telefonos de Costa Rica o WhatsApp. El contacto va por la plataforma."""
    return bool(_PATRON_TELEFONO.search(texto) or _PATRON_WHATSAPP.search(texto))


def tarifa_fija_de_cuenta(
    plan: PlanArtista, tarifas_abiertas: Iterable[Decimal], politicas: PoliticasPedido
) -> Decimal | None:
    """La tarifa a fijar en la cuenta conectada, o None si hay pedidos abiertos
    con otra tarifa: en ese caso el lote 8 la ajusta por operacion."""
    tarifa = tarifa_para_plan(plan, politicas)
    if all(abierta == tarifa for abierta in tarifas_abiertas):
        return tarifa
    return None


class _PerfilCobrable(Protocol):
    rol: RolPerfil
    pasarela_cuenta_id: str | None
    pasarela_onboarding: EstadoOnboarding


def puede_cobrar(perfil: _PerfilCobrable) -> bool:
    return (
        perfil.rol == RolPerfil.ARTISTA
        and perfil.pasarela_cuenta_id is not None
        and perfil.pasarela_onboarding == EstadoOnboarding.COMPLETADO
    )
