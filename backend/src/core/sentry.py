import sentry_sdk

from src.core.config import Settings


def configurar_sentry(config: Settings) -> bool:
    """Inicia Sentry si hay DSN. Devuelve si quedo activo."""
    if not config.SENTRY_DSN:
        return False
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        environment=config.ENVIRONMENT,
        traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        # Sin cabeceras, IP ni variables locales: pueden llevar tokens de sesion
        send_default_pii=False,
        include_local_variables=False,
    )
    return True
