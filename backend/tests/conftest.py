import asyncio
import sys
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import (
    get_almacenamiento,
    get_current_user_payload,
    get_db,
    get_pasarela,
)
from src.core.config import settings
from src.main import app
from src.payments.falsa import PasarelaFalsa
from src.storage.falso import AlmacenamientoFalso

if sys.platform == "win32":
    # pluggy casa los argumentos del hook por nombre: no se pueden renombrar
    def pytest_asyncio_loop_factories(config, item):  # noqa: ARG001
        # psycopg async no funciona con el loop Proactor, que es el de Windows
        return {"selector": asyncio.SelectorEventLoop}


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


@pytest_asyncio.fixture
async def sesion_api(test_db) -> AsyncSession:
    """Sesion que comparten la prueba y los handlers. Los commit de los handlers
    liberan savepoints: al final todo se deshace con el rollback externo."""
    async with test_db.connect() as conexion:
        transaccion = await conexion.begin()
        session = AsyncSession(
            bind=conexion,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )

        async def _get_db():
            yield session

        app.dependency_overrides[get_db] = _get_db
        try:
            yield session
        finally:
            app.dependency_overrides.pop(get_db, None)
            await session.close()
            await transaccion.rollback()


@pytest.fixture
def pasarela_falsa():
    pasarela = PasarelaFalsa()
    app.dependency_overrides[get_pasarela] = lambda: pasarela
    yield pasarela
    app.dependency_overrides.pop(get_pasarela, None)


@pytest.fixture
def autenticar_como():
    """Llamala con un uuid para que las peticiones lleguen autenticadas como el."""

    def _autenticar(user_id: uuid.UUID) -> None:
        payload = {"sub": str(user_id)}
        app.dependency_overrides[get_current_user_payload] = lambda: payload

    yield _autenticar
    app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.fixture
def almacenamiento_falso():
    almacenamiento = AlmacenamientoFalso()
    app.dependency_overrides[get_almacenamiento] = lambda: almacenamiento
    yield almacenamiento
    app.dependency_overrides.pop(get_almacenamiento, None)
    almacenamiento.limpiar()
