"""Webhook de la pasarela (D29).

Sin autenticacion de usuario: el origen lo prueba `parsear_webhook`. Se
procesa en la misma peticion y no en el worker, porque la pasarela falsa vive
en la memoria de este proceso. Primero se guarda y se confirma el evento, y
recien despues se procesa en otra transaccion: responde 200 aunque el proceso
falle, y el barrido lo reintenta.
"""

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status

from src.api.deps import Pasarela, Sesion
from src.core.config import settings
from src.domain.politicas import PoliticasPedido
from src.payments.errores import FirmaInvalida, OperacionNoSoportada, SolicitudInvalida
from src.schemas.pagos import WebhookRespuesta
from src.services import webhooks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pagos", tags=["pagos"])

# Procesar solo consulta la pasarela: cortarlo a mitad de camino es seguro.
# Responde antes de que el proveedor se canse de esperar (pregunta 17 a ONVO)
TIEMPO_MAXIMO_PROCESO_SEGUNDOS = 8


@router.post("/webhook")
async def webhook(
    request: Request, session: Sesion, pasarela: Pasarela
) -> WebhookRespuesta:
    cuerpo = await request.body()
    try:
        evento = await webhooks.recibir(
            session, pasarela, cuerpo, dict(request.headers)
        )
    except FirmaInvalida as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "El origen del webhook no es valido"
        ) from exc
    except SolicitudInvalida as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "El webhook no tiene un formato valido"
        ) from exc
    except OperacionNoSoportada as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "El webhook no esta configurado"
        ) from exc
    await session.commit()
    if evento.procesado_en is not None:
        return WebhookRespuesta(estado="repetido")

    evento_id = evento.id
    try:
        async with asyncio.timeout(TIEMPO_MAXIMO_PROCESO_SEGUNDOS):
            await webhooks.procesar(
                session,
                pasarela,
                evento_id,
                ahora=datetime.now(UTC),
                politicas=PoliticasPedido.desde_config(settings),
            )
            await session.commit()
    # Sin el mensaje: puede traer datos de la pasarela
    except Exception as exc:  # noqa: BLE001  el barrido lo reintenta
        await session.rollback()
        logger.warning(
            "Webhook: fallo procesar el evento %s (%s)", evento_id, type(exc).__name__
        )
        await webhooks.registrar_fallo(session, evento_id, type(exc).__name__)
        await session.commit()
    return WebhookRespuesta(estado="recibido")
