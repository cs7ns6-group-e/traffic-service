import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from shared.auth import CurrentUser, get_current_user
from app.main import app


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
            if key in store:
                return False
            store[key] = "1"
            return True

        def release_lock(self, key):
            store.pop(key, None)

        def make_key(self, *parts):
            return ":".join(parts)

    return FakeCache()


@pytest_asyncio.fixture
async def async_client(mock_current_user):
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
