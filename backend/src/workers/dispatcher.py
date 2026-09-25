from .handlers.embeddings import handle_generate_embedding
from .handlers.moderation import handle_moderate_image
from .handlers.styles import handle_classify_style
from .handlers.thumbnails import handle_generate_thumbnail

# Registro central de los jobs permitidos y sus handlers
HANDLERS = {
    "generate_thumbnail": handle_generate_thumbnail,
    "generate_embedding": handle_generate_embedding,
    "classify_style": handle_classify_style,
    "moderate_image": handle_moderate_image,
}


async def dispatch_job(job_type: str, payload: dict):
    """Encuentra el handler correcto y lo ejecuta."""
    handler = HANDLERS.get(job_type)
    if not handler:
        raise ValueError(f"No hay handler registrado para el tipo de job: {job_type}")

    await handler(payload)
