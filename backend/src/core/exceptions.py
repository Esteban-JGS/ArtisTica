class ArtisTicaException(Exception):
    """Clase base para excepciones del dominio."""


class ResourceNotFound(ArtisTicaException):
    pass


class InvalidStateTransition(ArtisTicaException):
    pass
