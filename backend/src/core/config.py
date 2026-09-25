from decimal import Decimal

from pydantic import AnyHttpUrl, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "ArtisTica"
    API_V1_STR: str = "/api/v1"

    # Supabase / Database
    # Puerto 6543, pooler (Supavisor)
    DATABASE_URL: PostgresDsn
    # Puerto 5432, conexion directa para Alembic
    ALEMBIC_DATABASE_URL: PostgresDsn

    SUPABASE_URL: AnyHttpUrl
    # Clave service_role: salta RLS. Solo servidor, jamas en el cliente movil.
    SUPABASE_SERVICE_KEY: str | None = None

    # Environment
    ENVIRONMENT: str = "dev"
    SENTRY_DSN: str | None = None

    # Pasarela de pagos. Texto libre: la valida src.payments.fabrica
    PASARELA: str = "falsa"

    # Politicas de pedido (D5). Unico lugar donde viven sus valores por defecto.
    ANTICIPO_PORCENTAJE_MINIMO: Decimal = Decimal("30")
    ANTICIPO_PORCENTAJE_MAXIMO: Decimal = Decimal("50")
    ANTICIPO_PORCENTAJE_DEFECTO: Decimal = Decimal("50")
    DIAS_VENTANA_DISPUTA: int = 7
    CANCELACION_EVENTO_DIAS_TOTAL: int = 30
    CANCELACION_EVENTO_DIAS_PARCIAL: int = 7
    CANCELACION_EVENTO_PORCENTAJE_PARCIAL: Decimal = Decimal("50")
    MONTO_MINIMO_PEDIDO: Decimal = Decimal("2500.00")
    TARIFA_TALLER_PORCENTAJE: Decimal = Decimal("8")
    TARIFA_ESTUDIO_PORCENTAJE: Decimal = Decimal("5")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


settings = Settings()
