"""Taxonomia de errores de la pasarela.

Quien reintenta un job mira solo `reintentable`. Ningun mensaje lleva secretos.
"""


class ErrorPasarela(Exception):
    """Base de todo error de la capa de pagos."""

    reintentable: bool = False

    def __init__(self, mensaje: str, *, reintentable: bool | None = None) -> None:
        super().__init__(mensaje)
        if reintentable is not None:
            self.reintentable = reintentable


class PagoRechazado(ErrorPasarela):
    """La pasarela rechazo el pago: fondos, tarjeta, antifraude."""


class PasarelaNoDisponible(ErrorPasarela):
    """Timeout, 5xx o red.

    Es reintentable salvo que el resultado quede incierto en una operacion que
    no se puede repetir sin riesgo de duplicar el efecto. Ver `PasarelaOnvo`.
    """

    reintentable = True


class CredencialesInvalidas(ErrorPasarela):
    """401, 403 o falta la clave. Es un error de configuracion."""


class SolicitudInvalida(ErrorPasarela):
    """Datos incoherentes con el estado del cobro o con la solicitud previa."""


class AutorizacionVencida(ErrorPasarela):
    """Se intento capturar una autorizacion que ya vencio."""


class OperacionNoSoportada(ErrorPasarela):
    """La operacion o el metodo no esta en las capacidades del adaptador."""


class FirmaInvalida(ErrorPasarela):
    """El webhook no pasa la verificacion."""
