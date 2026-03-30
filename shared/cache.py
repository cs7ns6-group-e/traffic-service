import logging

import redis

logger = logging.getLogger(__name__)


class CacheClient:
    """Wraps redis-py with typed methods and key namespacing."""

    def __init__(self, redis_url: str, prefix: str = "trafficbook") -> None:
        self._prefix = prefix
        self._client = redis.from_url(redis_url, decode_responses=True)

    def make_key(self, *parts: str) -> str:
        return ":".join([self._prefix, *parts])

    def get(self, key: str) -> str | None:
        return self._client.get(self.make_key(key))

    def set(self, key: str, value: str, ttl: int = 30) -> None:
        self._client.setex(self.make_key(key), ttl, value)

    def delete(self, *keys: str) -> None:
        namespaced = [self.make_key(k) for k in keys]
        self._client.delete(*namespaced)

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(self.make_key(key)))

    def set_lock(self, key: str, ttl: int = 60) -> bool:
        """Atomic SETNX — returns True if lock acquired."""
        lock_key = self.make_key("lock", key)
        result = self._client.set(lock_key, "1", nx=True, ex=ttl)
        return bool(result)

    def release_lock(self, key: str) -> None:
        lock_key = self.make_key("lock", key)
        self._client.delete(lock_key)
