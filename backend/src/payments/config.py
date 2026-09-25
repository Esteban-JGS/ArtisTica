"""Configuracion propia del adaptador de ONVO. Solo la lee `src.payments`."""

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigOnvo(BaseSettings):
    # Opcional para que la app arranque con la falsa. La fabrica la exige
    # cuando PASARELA=onvo.
    API_KEY: SecretStr | None = None
    # Sin valor rige URL_BASE del bloque de mapeo de onvo.py
    BASE_URL: AnyHttpUrl | None = None
    # Sin valor, parsear_webhook se niega a aceptar eventos
    WEBHOOK_SECRET: SecretStr | None = None
    TIMEOUT_SEGUNDOS: int = Field(default=15, gt=0)

    model_config = SettingsConfigDict(
        env_prefix="ONVO_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
