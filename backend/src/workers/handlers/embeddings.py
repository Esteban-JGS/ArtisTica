async def handle_generate_embedding(payload: dict):
    """Generar embedding vectorial para un post y actualizar la columna pgvector."""
    # TODO: Integración con OpenAI (text-embedding-3) o un modelo de SentenceTransformers
