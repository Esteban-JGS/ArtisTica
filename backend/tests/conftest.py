import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings
from src.main import app


@pytest_asyncio.fixture(scope="session")
async def test_db():
    """Conexión principal a la base de datos de test (migraciones ya ejecutadas)."""
    engine = create_async_engine(str(settings.DATABASE_URL))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(test_db) -> AsyncSession:
    """Provee una sesión asíncrona de base de datos para los tests."""
    async_session_maker = async_sessionmaker(
        test_db, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client():
    """Cliente HTTP asíncrono pegándole a la app de FastAPI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
