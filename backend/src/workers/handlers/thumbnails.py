from io import BytesIO

from PIL import Image


async def handle_generate_thumbnail(_payload: dict):
    """
    Genera un thumbnail usando Pillow.
    payload esperado: {"storage_path": "...", "asset_id": "..."}
    """
    # TODO: Descargar el archivo original desde Supabase Storage con la
    # storage_path del payload. Mientras tanto se redimensiona un canvas en
    # blanco, para demostrar que la logica base y Pillow funcionan.
    img = Image.new("RGB", (1000, 1000), color="black")

    # Crear miniatura (mantiene aspect ratio)
    img.thumbnail((300, 300))

    out = BytesIO()
    img.save(out, format="JPEG")

    # TODO: Subir el buffer comprimido (out.getvalue()) de vuelta a Storage
    # TODO: Actualizar la DB indicando que el thumbnail_path ya existe
