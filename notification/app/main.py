import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.exceptions import register_exception_handlers
from shared.health import create_health_router
from shared.logging import setup_logging
from shared.messaging import EventConsumer

from app.config import get_settings
from app.consumer import BookingEventConsumer

logger = logging.getLogger(__name__)
settings = get_settings()
consumer: BookingEventConsumer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer
    setup_logging(settings.app_name, settings.debug)
    consumer = BookingEventConsumer(settings)
    consumer.start_background()
    logger.info("Notification service started")
    yield
    if consumer:
        consumer.stop()
    logger.info("Notification service shutdown")


app = FastAPI(title="Notification Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
health_router = create_health_router("notification", [])
app.include_router(health_router)
