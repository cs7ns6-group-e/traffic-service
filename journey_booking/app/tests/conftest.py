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
def mock_authority_user():
    return CurrentUser(
        id="auth-1", email="authority@test.com", name="Authority User", roles=["traffic_authority"]
    )


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
            if key in store:
                return False
            store[key] = "1"
            return True

        def release_lock(self, key):
            store.pop(key, None)

        def make_key(self, *parts):
            return ":".join(parts)

    return FakeCache()


@pytest.fixture
def mock_publisher():
    events = []

    class FakePublisher:
        def connect(self):
            pass

        def publish(self, queue, event):
            events.append({"queue": queue, "event": event})

        def close(self):
            pass

        @property
        def published(self):
            return events

    return FakePublisher()


@pytest_asyncio.fixture
async def async_client(db_session, mock_current_user):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
