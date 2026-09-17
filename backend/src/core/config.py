from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, AnyHttpUrl
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "ArtisTica"
    API_V1_STR: str = "/api/v1"
    
    # Supabase / Database
    # Puerto 6543, pooler (Supavisor)
    DATABASE_URL: PostgresDsn
    # Puerto 5432, conexion directa para Alembic
    ALEMBIC_DATABASE_URL: PostgresDsn
    
    SUPABASE_URL: AnyHttpUrl
    SUPABASE_JWT_SECRET: str
    
    # Environment
    ENVIRONMENT: str = "dev"
    SENTRY_DSN: Optional[str] = None
    
    # Commission Configuration
    DAYS_UNTIL_AUTO_RELEASE: int = 14
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
