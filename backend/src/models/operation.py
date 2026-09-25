# Se conserva solo porque src/workers/main.py importa Job desde aqui.
from .operacion import Job

__all__ = ["Job"]
