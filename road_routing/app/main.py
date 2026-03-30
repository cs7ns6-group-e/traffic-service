import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.exceptions import register_exception_handlers
from shared.health import create_health_router
from shared.logging import setup_logging

from app.config import get_settings
from app.routes.routing import router as routing_router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.app_name, settings.debug)
    logger.info("Road routing service started")
    yield
    logger.info("Road routing service shutdown")


app = FastAPI(title="Road Routing Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(routing_router, prefix="", tags=["routing"])
health_router = create_health_router("road_routing", [])
app.include_router(health_router)
