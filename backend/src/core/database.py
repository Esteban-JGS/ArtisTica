from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.core.config import settings

# Supavisor en transaction mode no soporta prepared statements.
# Por eso usamos prepare_threshold=None y statement_cache_size=0
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=False,
    connect_args={
        "prepare_threshold": None,
        "statement_cache_size": 0,
    }
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)
