"""Worker de la cola de trabajos, contra una base migrada.

Casi todas usan `sesiones_prueba`, que termina en rollback. La prueba 3
necesita commits de verdad para ver el job desde otra conexion: crea su job y
lo borra al final.
"""

import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models import Job
from src.workers.main import (
    cerrar_job,
    procesar_uno,
    recuperar_colgados,
    tomar_job,
)

AHORA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
ESTE = "worker-este"
OTRO = "worker-otro"
QUINCE_MINUTOS = timedelta(minutes=15)


@pytest_asyncio.fixture
async def sesiones(sesiones_prueba) -> async_sessionmaker[AsyncSession]:
    """Cola vacia dentro de la transaccion de la prueba: el rollback la repone."""
    async with sesiones_prueba.begin() as session:
        await session.execute(delete(Job))
    return sesiones_prueba


async def nuevo_job(sesiones, **campos) -> uuid.UUID:
    datos = {
        "type": "prueba",
        "payload": {"n": 1},
        "status": "pending",
        "run_after": AHORA - timedelta(minutes=1),
    }
    datos.update(campos)
    job = Job(id=uuid.uuid4(), **datos)
    async with sesiones.begin() as session:
        session.add(job)
    return job.id


async def leer(sesiones, job_id) -> Job:
    async with sesiones() as session:
        return await session.get(Job, job_id)


async def sin_error(_tipo: str, _payload: dict) -> None:
    return None


async def con_error(_tipo: str, _payload: dict) -> None:
    raise RuntimeError("el handler fallo")


# 1. Tomar


async def test_9_w01_tomar_marca_processing_y_no_se_repite(sesiones):
    job_id = await nuevo_job(sesiones)

    tomado = await tomar_job(sesiones, ahora=AHORA, worker_id=ESTE)
    assert tomado is not None
    assert (tomado.id, tomado.type, tomado.payload) == (job_id, "prueba", {"n": 1})
    job = await leer(sesiones, job_id)
    assert job.status == "processing"
    assert (job.locked_at, job.locked_by) == (AHORA, ESTE)

    assert await tomar_job(sesiones, ahora=AHORA, worker_id=OTRO) is None


async def test_9_w01_no_toma_un_job_que_todavia_no_toca(sesiones):
    await nuevo_job(sesiones, run_after=AHORA + timedelta(seconds=1))
    assert await tomar_job(sesiones, ahora=AHORA, worker_id=ESTE) is None


# 2. Cierre


async def test_9_w02_job_exitoso_queda_completed(sesiones):
    job_id = await nuevo_job(sesiones)

    assert await procesar_uno(
        sesiones, ahora=AHORA, worker_id=ESTE, despachar=sin_error
    )
    job = await leer(sesiones, job_id)
    assert job.status == "completed"
    assert (job.locked_at, job.locked_by, job.attempts) == (None, None, 0)


async def test_9_w02_job_fallido_reintenta_con_backoff_y_muere(sesiones):
    job_id = await nuevo_job(sesiones)

    assert await procesar_uno(
        sesiones, ahora=AHORA, worker_id=ESTE, despachar=con_error
    )
    job = await leer(sesiones, job_id)
    assert job.status == "pending"
    assert job.attempts == 1
    assert job.run_after == AHORA + timedelta(minutes=2)
    assert "el handler fallo" in job.last_error
    assert (job.locked_at, job.locked_by) == (None, None)

    ultimo = await nuevo_job(sesiones, attempts=2, max_attempts=3)
    await procesar_uno(sesiones, ahora=AHORA, worker_id=ESTE, despachar=con_error)
    job = await leer(sesiones, ultimo)
    assert job.status == "dead"
    assert job.attempts == 3


async def test_9_w02_sin_jobs_devuelve_false(sesiones):
    assert not await procesar_uno(
        sesiones, ahora=AHORA, worker_id=ESTE, despachar=sin_error
    )


# 3. El handler corre fuera de la transaccion


@pytest_asyncio.fixture
async def sesiones_reales(test_db):
    """Commits de verdad. Lo que crea la prueba lo borra el finalizador."""
    sesiones = async_sessionmaker(test_db, class_=AsyncSession, expire_on_commit=False)
    creados: list[uuid.UUID] = []
    yield sesiones, creados
    async with sesiones.begin() as session:
        await session.execute(delete(Job).where(Job.id.in_(creados)))


async def test_9_w03_el_handler_corre_fuera_de_la_transaccion(sesiones_reales):
    sesiones, creados = sesiones_reales
    viejo = datetime(2000, 1, 1, tzinfo=UTC)
    job_id = uuid.uuid4()
    creados.append(job_id)
    async with sesiones.begin() as session:
        session.add(
            Job(
                id=job_id,
                type="prueba_fuera_de_transaccion",
                payload={},
                status="pending",
                run_after=viejo,
                created_at=viejo,
            )
        )
    vistos: list[tuple[str, str | None]] = []

    async def handler(tipo: str, _payload: dict) -> None:
        assert tipo == "prueba_fuera_de_transaccion"
        # Otra conexion: ve el job confirmado y sin bloqueo
        async with sesiones() as otra:
            stmt = select(Job).where(Job.id == job_id).with_for_update(nowait=True)
            job = (await otra.execute(stmt)).scalar_one()
            vistos.append((job.status, job.locked_by))

    assert await procesar_uno(
        sesiones, ahora=datetime.now(UTC), worker_id=ESTE, despachar=handler
    )
    assert vistos == [("processing", ESTE)]
    async with sesiones() as session:
        assert (await session.get(Job, job_id)).status == "completed"


# 4. Jobs colgados


async def test_9_w04_recupera_un_processing_viejo_y_no_uno_reciente(sesiones):
    viejo = await nuevo_job(
        sesiones,
        status="processing",
        locked_at=AHORA - QUINCE_MINUTOS - timedelta(seconds=1),
        locked_by=OTRO,
    )
    reciente = await nuevo_job(
        sesiones,
        status="processing",
        locked_at=AHORA - timedelta(minutes=1),
        locked_by=OTRO,
    )

    recuperados = await recuperar_colgados(
        sesiones, ahora=AHORA, tiempo_maximo=QUINCE_MINUTOS
    )
    assert recuperados == 1
    job = await leer(sesiones, viejo)
    assert job.status == "pending"
    assert job.attempts == 1
    assert job.run_after == AHORA + timedelta(minutes=2)
    assert "tiempo maximo" in job.last_error
    assert (job.locked_at, job.locked_by) == (None, None)
    job = await leer(sesiones, reciente)
    assert (job.status, job.attempts, job.locked_by) == ("processing", 0, OTRO)


async def test_9_w04_un_colgado_en_el_ultimo_intento_muere(sesiones):
    job_id = await nuevo_job(
        sesiones,
        status="processing",
        attempts=2,
        locked_at=AHORA - timedelta(hours=1),
        locked_by=OTRO,
    )
    await recuperar_colgados(sesiones, ahora=AHORA, tiempo_maximo=QUINCE_MINUTOS)
    job = await leer(sesiones, job_id)
    assert (job.status, job.attempts) == ("dead", 3)


# 5. Cerrar no pisa un job ajeno


async def test_9_w05_cerrar_no_pisa_un_job_recuperado_por_otro(sesiones):
    job_id = await nuevo_job(sesiones)
    tomado = await tomar_job(sesiones, ahora=AHORA, worker_id=ESTE)
    # Se colgo: se recupera y otro worker lo toma
    await recuperar_colgados(
        sesiones, ahora=AHORA + timedelta(hours=1), tiempo_maximo=QUINCE_MINUTOS
    )
    await tomar_job(sesiones, ahora=AHORA + timedelta(hours=2), worker_id=OTRO)

    await cerrar_job(sesiones, tomado.id, worker_id=ESTE, error=None, ahora=AHORA)
    job = await leer(sesiones, job_id)
    assert (job.status, job.locked_by, job.attempts) == ("processing", OTRO, 1)


async def test_9_w05_cerrar_no_toca_un_job_ya_recuperado(sesiones):
    job_id = await nuevo_job(sesiones)
    tomado = await tomar_job(sesiones, ahora=AHORA, worker_id=ESTE)
    await recuperar_colgados(
        sesiones, ahora=AHORA + timedelta(hours=1), tiempo_maximo=QUINCE_MINUTOS
    )

    await cerrar_job(sesiones, tomado.id, worker_id=ESTE, error="tarde", ahora=AHORA)
    job = await leer(sesiones, job_id)
    assert (job.status, job.attempts) == ("pending", 1)
    assert "tarde" not in job.last_error


# 6. Importar no instala manejadores de senales


def test_9_w06_importar_no_instala_manejadores_de_senales():
    codigo = (
        "import signal\n"
        "antes = signal.getsignal(signal.SIGINT)\n"
        "import src.workers.main\n"
        "assert signal.getsignal(signal.SIGINT) is antes\n"
        "assert signal.getsignal(signal.SIGINT) is signal.default_int_handler\n"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
