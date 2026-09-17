import asyncio
import signal
import socket
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.models.operation import Job
from src.workers.dispatcher import dispatch_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

WORKER_ID = socket.gethostname()
shutdown_event = asyncio.Event()

def handle_sigterm(*args):
    logger.info("SIGTERM recibido. Iniciando apagado limpio del worker. Se terminará el job actual antes de salir.")
    shutdown_event.set()

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

async def worker_loop():
    logger.info(f"Worker {WORKER_ID} iniciado. Esperando trabajos en la cola...")
    while not shutdown_event.is_set():
        try:
            async with AsyncSessionLocal() as session:
                now = datetime.now(timezone.utc)
                
                # Obtener un solo trabajo bloqueando la fila exclusivamente y esquivando los ya bloqueados
                stmt = select(Job).where(
                    Job.status == "pending",
                    Job.run_after <= now
                ).order_by(Job.created_at).limit(1).with_for_update(skip_locked=True)
                
                result = await session.execute(stmt)
                job = result.scalars().first()
                
                if not job:
                    # No hay jobs listos, pausar un instante
                    await asyncio.sleep(2)
                    continue
                
                job.locked_at = now
                job.locked_by = WORKER_ID
                job.status = "processing"
                
                # Reflejar el lock en la base para mayor seguridad (aunque FOR UPDATE ya lo protege)
                await session.flush() 
                
                logger.info(f"Procesando job {job.id} de tipo {job.type}")
                try:
                    await dispatch_job(job.type, job.payload)
                    job.status = "completed"
                    logger.info(f"Job {job.id} completado con éxito")
                except Exception as e:
                    logger.error(f"Error en job {job.id}: {e}")
                    job.attempts += 1
                    job.last_error = str(e)
                    
                    if job.attempts >= job.max_attempts:
                        job.status = "dead"
                        logger.warning(f"Job {job.id} superó intentos y fue marcado como dead.")
                    else:
                        job.status = "pending"
                        # Backoff exponencial: 2, 4, 8, 16... minutos
                        job.run_after = now + timedelta(minutes=2**job.attempts)
                finally:
                    job.locked_at = None
                    job.locked_by = None
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"Error inesperado en loop principal: {e}")
            await asyncio.sleep(5)
            
    logger.info("Worker detenido limpiamente.")

if __name__ == "__main__":
    asyncio.run(worker_loop())
