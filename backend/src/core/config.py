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

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


settings = Settings()
