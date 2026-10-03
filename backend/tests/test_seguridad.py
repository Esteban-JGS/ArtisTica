"""Verificacion del JWT de Supabase. Sin red: el JWKS se reemplaza con monkeypatch."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from src.core import security

KID = "clave-prueba"
CLAVE_PRIVADA = ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(autouse=True)
def jwks_local(monkeypatch):
    clave = SimpleNamespace(key=CLAVE_PRIVADA.public_key())
    monkeypatch.setattr(
        security.jwks_client, "get_signing_key_from_jwt", lambda _token: clave
    )


def _claims(**cambios) -> dict:
    ahora = datetime.now(UTC)
    claims = {
        "sub": "6f1c2a4e-0000-4000-8000-000000000001",
        "aud": "authenticated",
        "iss": security.ISSUER,
        "iat": ahora,
        "exp": ahora + timedelta(hours=1),
    }
    claims.update(cambios)
    return claims


def _token(**cambios) -> str:
    return jwt.encode(
        _claims(**cambios), CLAVE_PRIVADA, algorithm="ES256", headers={"kid": KID}
    )


def test_01_token_valido_devuelve_el_payload():
    payload = security.verify_token(_token())
    assert payload["sub"] == "6f1c2a4e-0000-4000-8000-000000000001"
    assert payload["aud"] == "authenticated"


@pytest.mark.parametrize(
    "cambios",
    [
        {"exp": datetime.now(UTC) - timedelta(minutes=5)},
        {"aud": "anon"},
        {"iss": "https://otro.supabase.co/auth/v1"},
    ],
    ids=["vencido", "aud_distinto", "iss_distinto"],
)
def test_02_token_invalido_da_401_con_causa(cambios):
    with pytest.raises(HTTPException) as info:
        security.verify_token(_token(**cambios))
    assert info.value.status_code == 401
    assert info.value.__cause__ is not None or info.value.__suppress_context__


def test_03_token_hs256_da_401():
    token = jwt.encode(
        _claims(), "secreto-compartido-de-al-menos-32-bytes", algorithm="HS256"
    )
    with pytest.raises(HTTPException) as info:
        security.verify_token(token)
    assert info.value.status_code == 401


def test_04_jwks_url_es_la_de_supabase():
    assert security.JWKS_URL.endswith("/auth/v1/.well-known/jwks.json")
