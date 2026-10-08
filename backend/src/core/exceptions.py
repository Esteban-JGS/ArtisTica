class ArtisTicaException(Exception):
    """Clase base para excepciones del dominio."""


class ResourceNotFound(ArtisTicaException):
    pass


class InvalidStateTransition(ArtisTicaException):
    pass


class ReglaDeNegocioViolada(ArtisTicaException):
    """La operacion tiene forma valida pero una politica del negocio la impide."""


class CotizacionInvalida(ReglaDeNegocioViolada):
    pass


class ObraNoDisponible(ReglaDeNegocioViolada):
    pass


class ActorNoAutorizado(ReglaDeNegocioViolada):
    pass


class FueraDePlazo(ReglaDeNegocioViolada):
    pass


class LimiteExcedido(ReglaDeNegocioViolada):
    """Se paso un limite de uso, como las consultas de una cuenta nueva. Da 429."""


class HechosInconsistentes(ReglaDeNegocioViolada):
    """Los hechos de la pasarela no coinciden con el plan que exige el dominio."""


class PerfilYaRegistrado(ReglaDeNegocioViolada):
    pass


class HandleNoDisponible(ReglaDeNegocioViolada):
    pass


class CobroNoHabilitado(ReglaDeNegocioViolada):
    """El artista no completo el onboarding de la pasarela."""
