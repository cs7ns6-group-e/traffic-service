import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.database import init_db
from shared.exceptions import register_exception_handlers
from shared.health import create_health_router
from shared.logging import setup_logging
from shared.messaging import EventPublisher

from app.config import get_settings
from app.routes.journeys import router as journeys_router

logger = logging.getLogger(__name__)

settings = get_settings()
publisher = EventPublisher(settings.rabbitmq_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.app_name, settings.debug)
    await init_db()
    try:
        publisher.connect()
        logger.info("RabbitMQ publisher connected")
    except Exception as exc:
        logger.warning("RabbitMQ unavailable at startup: %s", exc)
    yield
    publisher.close()
    logger.info("Journey booking service shutdown complete")


app = FastAPI(
    title="Journey Booking Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(journeys_router, prefix="/journeys", tags=["journeys"])
health_router = create_health_router("journey_booking", [])
app.include_router(health_router)
