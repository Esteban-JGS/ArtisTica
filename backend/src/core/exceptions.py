class ArtisTicaException(Exception):
    """Clase base para excepciones del dominio."""
    pass

class ResourceNotFound(ArtisTicaException):
    pass

class InvalidStateTransition(ArtisTicaException):
    pass
