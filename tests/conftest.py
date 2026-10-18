import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import get_db
from app.models.base import Base
from app.models.auth import Organizer, SensorClient
from app.services.auth_service import AuthService
from app.main import app

# In-memory SQLite async engine for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def organizer_token(client: AsyncClient, db_session: AsyncSession) -> str:
    # Seed organizer
    email = "test-organizer@campus.edu"
    password = "SecurePassword123!"
    organizer = Organizer(
        email=email,
        password_hash=AuthService.hash_password(password),
        role="organizer",
        is_active=True
    )
    db_session.add(organizer)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def sensor_api_key(db_session: AsyncSession) -> str:
    raw_key, hashed_key = AuthService.generate_sensor_api_key()
    client_obj = SensorClient(
        name="test-sensor-client",
        api_key_hash=hashed_key,
        is_active=True
    )
    db_session.add(client_obj)
    await db_session.commit()
    return raw_key
