import asyncio
import logging

import pika
import pika.exceptions
from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.cache import CacheClient
from shared.schemas import HealthResponse

logger = logging.getLogger(__name__)


async def check_database(db: AsyncSession) -> dict:
    try:
        await db.execute(text("SELECT 1"))
        return {"database": "ok"}
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return {"database": f"error: {exc}"}


async def check_redis(cache: CacheClient) -> dict:
    try:
        cache.get("healthcheck")
        return {"redis": "ok"}
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        return {"redis": f"error: {exc}"}


async def check_rabbitmq(url: str) -> dict:
    try:
        params = pika.URLParameters(url)
        connection = pika.BlockingConnection(params)
        connection.close()
        return {"rabbitmq": "ok"}
    except Exception as exc:
        logger.error("RabbitMQ health check failed: %s", exc)
        return {"rabbitmq": f"error: {exc}"}


def create_health_router(service_name: str, checks: list) -> APIRouter:
    """Creates a /health router that runs all checks in parallel."""
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        from shared.config import get_settings

        settings = get_settings()
        results = await asyncio.gather(*[check() for check in checks], return_exceptions=True)

        combined: dict = {}
        for result in results:
            if isinstance(result, Exception):
                combined[f"check_{len(combined)}"] = f"error: {result}"
            elif isinstance(result, dict):
                combined.update(result)

        overall = "ok" if all("error" not in str(v) for v in combined.values()) else "degraded"

        return HealthResponse(
            service=service_name,
            status=overall,
            region=settings.region,
        )

    return router
