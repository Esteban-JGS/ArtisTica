import logging

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from src.core.config import settings

logger = logging.getLogger(__name__)

# Configuración para Supabase Auth
SUPABASE_URL = str(settings.SUPABASE_URL).rstrip("/")
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
ISSUER = f"{SUPABASE_URL}/auth/v1"

# Solo algoritmos asimetricos: Supabase firma con ES256 (recomendado) o RS256.
# Un algoritmo simetrico permitiria firmar tokens con la clave publica.
ALGORITMOS = ["ES256", "RS256"]

# El cliente JWK obtiene las claves de Supabase y las cachea para evitar
# requests repetidos en cada autenticación (las claves rotan poco).
jwks_client = PyJWKClient(JWKS_URL, cache_keys=True, cache_jwk_set=True, lifespan=3600)


def _no_autorizado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_token(token: str) -> dict:
    """
    Verifica el JWT generado por Supabase.
    Valida la firma contra el JWKS, y los claims exp, aud e iss.
    Es sincronica: puede hacer una peticion HTTP al JWKS si no esta en cache.
    """
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Supabase usa 'authenticated' para el claim aud de usuarios con sesión
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=ALGORITMOS,
            audience="authenticated",
            issuer=ISSUER,
            options={
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
                "verify_signature": True,
            },
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        logger.warning("Token expirado")
        raise _no_autorizado("Token expirado") from e
    except jwt.InvalidTokenError as e:
        logger.warning("Token inválido: %s", type(e).__name__)
        raise _no_autorizado("Token inválido") from e
    except Exception as e:
        # Un JWKS caido no puede devolver 500 con detalles
        logger.error("Error imprevisto verificando token: %s", type(e).__name__)
        raise _no_autorizado("Error validando credenciales") from e
