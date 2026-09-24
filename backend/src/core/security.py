import logging

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from src.core.config import settings

logger = logging.getLogger(__name__)

# Configuración para Supabase Auth
SUPABASE_URL = str(settings.SUPABASE_URL).rstrip("/")
JWKS_URL = f"{SUPABASE_URL}/auth/v1/jwks"
ISSUER = f"{SUPABASE_URL}/auth/v1"

# El cliente JWK obtiene las claves de Supabase y las cachea para evitar
# requests repetidos en cada autenticación (las claves rotan poco).
jwks_client = PyJWKClient(JWKS_URL, cache_keys=True, cache_jwk_set=True, lifespan=3600)


def verify_token(token: str) -> dict:
    """
    Verifica el JWT generado por Supabase.
    Valida la firma contra el JWKS, y los claims exp, aud e iss.
    """
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Supabase usa 'authenticated' para el claim aud de usuarios con sesión
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
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
    except jwt.ExpiredSignatureError:
        logger.warning("Token expirado")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token inválido: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Error imprevisto verificando token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error validando credenciales",
            headers={"WWW-Authenticate": "Bearer"},
        )
