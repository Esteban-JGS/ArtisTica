from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings

# Supavisor en transaction mode no soporta prepared statements.
# Por eso psycopg usa prepare_threshold=None.
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=False,
    connect_args={
        "prepare_threshold": None,
    },
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)
