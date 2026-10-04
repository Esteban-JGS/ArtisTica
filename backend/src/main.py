import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.api.v1.router import api_router
from src.core.config import settings
from src.core.exceptions import (
    ActorNoAutorizado,
    InvalidStateTransition,
    ReglaDeNegocioViolada,
    ResourceNotFound,
)
from src.payments.errores import ErrorPasarela, PasarelaNoDisponible
from src.storage import AlmacenamientoNoDisponible, ErrorAlmacenamiento

logger = logging.getLogger(__name__)

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=1.0,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Logica de inicializacion (ej. cargar configuraciones, pre-calentar caches)
    yield
    # Logica de apagado


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_V1_STR)


# Manejadores de error. Starlette elige el de la clase mas especifica.


def _respuesta(codigo: int, detalle: str) -> JSONResponse:
    return JSONResponse(status_code=codigo, content={"detail": detalle})


async def _no_encontrado(_: Request, exc: Exception) -> JSONResponse:
    return _respuesta(status.HTTP_404_NOT_FOUND, str(exc))


async def _no_autorizado(_: Request, exc: Exception) -> JSONResponse:
    return _respuesta(status.HTTP_403_FORBIDDEN, str(exc))


async def _conflicto(_: Request, exc: Exception) -> JSONResponse:
    return _respuesta(status.HTTP_409_CONFLICT, str(exc))


async def _pasarela_no_disponible(_: Request, exc: Exception) -> JSONResponse:
    # El mensaje del proveedor no se copia: solo se loguea el tipo
    logger.warning("Pasarela no disponible: %s", type(exc).__name__)
    return _respuesta(
        status.HTTP_503_SERVICE_UNAVAILABLE, "La pasarela de pagos no esta disponible"
    )


async def _pasarela_rechazo(_: Request, exc: Exception) -> JSONResponse:
    logger.warning("La pasarela rechazo la operacion: %s", type(exc).__name__)
    return _respuesta(
        status.HTTP_502_BAD_GATEWAY, "La pasarela de pagos rechazo la operacion"
    )


async def _almacenamiento_no_disponible(_: Request, exc: Exception) -> JSONResponse:
    logger.warning("Almacenamiento no disponible: %s", type(exc).__name__)
    return _respuesta(
        status.HTTP_503_SERVICE_UNAVAILABLE, "El almacenamiento no esta disponible"
    )


async def _almacenamiento_rechazo(_: Request, exc: Exception) -> JSONResponse:
    logger.warning("El almacenamiento rechazo la operacion: %s", type(exc).__name__)
    return _respuesta(
        status.HTTP_502_BAD_GATEWAY, "El almacenamiento rechazo la operacion"
    )


app.add_exception_handler(ResourceNotFound, _no_encontrado)
app.add_exception_handler(ActorNoAutorizado, _no_autorizado)
app.add_exception_handler(InvalidStateTransition, _conflicto)
app.add_exception_handler(ReglaDeNegocioViolada, _conflicto)
app.add_exception_handler(PasarelaNoDisponible, _pasarela_no_disponible)
app.add_exception_handler(ErrorPasarela, _pasarela_rechazo)
app.add_exception_handler(AlmacenamientoNoDisponible, _almacenamiento_no_disponible)
app.add_exception_handler(ErrorAlmacenamiento, _almacenamiento_rechazo)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
