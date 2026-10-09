"""Worker de la cola de trabajos (tabla `jobs`).

Cada job se toma en una transaccion corta que lo marca `processing` y
confirma. El handler corre fuera de toda transaccion y el cierre va en otra:
un job lento no retiene ni la conexion ni el bloqueo. Un job que queda en
`processing` mas de JOB_TIEMPO_MAXIMO_MINUTOS (porque el worker murio a mitad
de camino) cuenta como un intento fallido y vuelve a la cola.

Un handler recibe solo el payload. Si necesita la base, abre su propia sesion.
"""

import asyncio
import logging
import os
import signal
import socket
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.models import Job
from src.workers.dispatcher import dispatch_job

logger = logging.getLogger(__name__)

# Unico por proceso: dos workers en la misma maquina no se pisan los jobs
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
PAUSA_SIN_JOBS_SEGUNDOS = 2
PAUSA_TRAS_ERROR_SEGUNDOS = 5
# Cada cuantas vueltas se buscan jobs colgados
VUELTAS_ENTRE_RECUPERACIONES = 60

PENDIENTE = "pending"
PROCESANDO = "processing"
COMPLETADO = "completed"
MUERTO = "dead"

Despachar = Callable[[str, dict], Awaitable[None]]
Sesiones = async_sessionmaker[AsyncSession]

parada = asyncio.Event()


@dataclass(frozen=True)
class JobTomado:
    id: uuid.UUID
    type: str
    payload: dict


def _ahora() -> datetime:
    return datetime.now(UTC)


def _soltar(job: Job) -> None:
    job.locked_at = None
    job.locked_by = None


def _registrar_fallo(job: Job, error: str, ahora: datetime) -> None:
    job.attempts += 1
    job.last_error = error
    if job.attempts >= job.max_attempts:
        job.status = MUERTO
        logger.warning("Job %s supero los intentos y quedo dead", job.id)
    else:
        job.status = PENDIENTE
        # Backoff exponencial: 2, 4, 8... minutos
        job.run_after = ahora + timedelta(minutes=2**job.attempts)
    _soltar(job)


async def recuperar_colgados(
    sesiones: Sesiones, *, ahora: datetime, tiempo_maximo: timedelta
) -> int:
    """Un job en processing por mas de `tiempo_maximo` cuenta como fallido."""
    async with sesiones.begin() as session:
        stmt = (
            select(Job)
            .where(Job.status == PROCESANDO, Job.locked_at < ahora - tiempo_maximo)
            .with_for_update(skip_locked=True)
        )
        jobs = list((await session.execute(stmt)).scalars())
        for job in jobs:
            _registrar_fallo(
                job,
                f"Supero el tiempo maximo de procesamiento ({tiempo_maximo})",
                ahora,
            )
    return len(jobs)


async def tomar_job(
    sesiones: Sesiones, *, ahora: datetime, worker_id: str
) -> JobTomado | None:
    """Marca processing el pending mas viejo y confirma enseguida."""
    async with sesiones.begin() as session:
        stmt = (
            select(Job)
            .where(Job.status == PENDIENTE, Job.run_after <= ahora)
            .order_by(Job.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = (await session.execute(stmt)).scalar_one_or_none()
        if job is None:
            return None
        job.status = PROCESANDO
        job.locked_at = ahora
        job.locked_by = worker_id
        return JobTomado(id=job.id, type=job.type, payload=job.payload)


async def cerrar_job(
    sesiones: Sesiones,
    job_id: uuid.UUID,
    *,
    worker_id: str,
    error: str | None,
    ahora: datetime,
) -> None:
    async with sesiones.begin() as session:
        stmt = select(Job).where(Job.id == job_id).with_for_update()
        job = (await session.execute(stmt)).scalar_one_or_none()
        if job is None or job.status != PROCESANDO or job.locked_by != worker_id:
            # Se colgo, otro worker lo recupero y ya no es de este
            logger.warning("Job %s ya no es de este worker: no se cierra", job_id)
            return
        if error is None:
            job.status = COMPLETADO
            _soltar(job)
        else:
            _registrar_fallo(job, error, ahora)


async def procesar_uno(
    sesiones: Sesiones,
    *,
    ahora: datetime,
    worker_id: str,
    despachar: Despachar = dispatch_job,
) -> bool:
    """Toma un job, lo ejecuta sin transaccion abierta y lo cierra. False si
    no habia ninguno listo."""
    job = await tomar_job(sesiones, ahora=ahora, worker_id=worker_id)
    if job is None:
        return False
    logger.info("Procesando job %s de tipo %s", job.id, job.type)
    error: str | None = None
    try:
        await despachar(job.type, job.payload)
    # El worker no puede caerse por un job: se registra y se reintenta
    except Exception as exc:
        logger.exception("Error en job %s", job.id)
        error = f"{type(exc).__name__}: {exc}"
    await cerrar_job(sesiones, job.id, worker_id=worker_id, error=error, ahora=ahora)
    return True


async def worker_loop() -> None:
    tiempo_maximo = timedelta(minutes=settings.JOB_TIEMPO_MAXIMO_MINUTOS)
    logger.info("Worker %s iniciado. Esperando trabajos en la cola...", WORKER_ID)
    vueltas = 0
    while not parada.is_set():
        try:
            if vueltas % VUELTAS_ENTRE_RECUPERACIONES == 0:
                recuperados = await recuperar_colgados(
                    AsyncSessionLocal, ahora=_ahora(), tiempo_maximo=tiempo_maximo
                )
                if recuperados:
                    logger.warning("Se recuperaron %s jobs colgados", recuperados)
            vueltas += 1
            hubo = await procesar_uno(
                AsyncSessionLocal, ahora=_ahora(), worker_id=WORKER_ID
            )
            if not hubo:
                await asyncio.sleep(PAUSA_SIN_JOBS_SEGUNDOS)
        # El loop no puede caerse: se registra, se espera y se sigue
        except Exception:
            logger.exception("Error inesperado en el loop del worker")
            await asyncio.sleep(PAUSA_TRAS_ERROR_SEGUNDOS)

    logger.info("Worker detenido limpiamente.")


def _pedir_parada(*_args: object) -> None:
    logger.info("Senal recibida: el worker termina el job actual y se detiene.")
    parada.set()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    signal.signal(signal.SIGTERM, _pedir_parada)
    signal.signal(signal.SIGINT, _pedir_parada)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
