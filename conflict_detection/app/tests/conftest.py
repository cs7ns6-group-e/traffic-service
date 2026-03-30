import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared.auth import CurrentUser, get_current_user
from shared.database import Base, get_db
from app.main import app

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def mock_current_user():
    return CurrentUser(id="user-1", email="driver@test.com", name="Test Driver", roles=["driver"])


@pytest.fixture
def mock_cache():
    store: dict = {}

    class FakeCache:
        def get(self, key):
            return store.get(key)

        def set(self, key, value, ttl=30):
            store[key] = value

        def delete(self, *keys):
            for k in keys:
                store.pop(k, None)

        def exists(self, key):
            return key in store

        def set_lock(self, key, ttl=60):
            lock_key = f"lock:{key}"
            if lock_key in store:
                return False
            store[lock_key] = "1"
            return True

        def release_lock(self, key):
            store.pop(f"lock:{key}", None)

        def make_key(self, *parts):
            return ":".join(parts)

    return FakeCache()
