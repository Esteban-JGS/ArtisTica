"""Reglas de los comentarios. Logica pura: recibe ids y devuelve ids o booleanos.

Hay un solo nivel de respuestas: responder a una respuesta cuelga la nueva del
mismo comentario de primer nivel.
"""

import uuid


def destino_de_respuesta(
    objetivo_id: uuid.UUID, objetivo_respuesta_a_id: uuid.UUID | None
) -> uuid.UUID:
    """De que comentario cuelga una respuesta al comentario `objetivo_id`."""
    if objetivo_respuesta_a_id is None:
        return objetivo_id
    return objetivo_respuesta_a_id


def puede_borrar(
    autor_id: uuid.UUID,
    artista_de_la_publicacion_id: uuid.UUID,
    usuario_id: uuid.UUID,
) -> bool:
    """El autor, o el artista que modera lo que se dice en su publicacion."""
    return usuario_id in (autor_id, artista_de_la_publicacion_id)
