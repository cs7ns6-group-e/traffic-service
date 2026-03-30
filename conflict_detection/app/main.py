import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.database import init_db
from shared.exceptions import register_exception_handlers
from shared.health import create_health_router
from shared.logging import setup_logging

from app.config import get_settings
from app.routes.conflicts import router as conflicts_router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.app_name, settings.debug)
    await init_db()
    logger.info("Conflict detection service started")
    yield
    logger.info("Conflict detection service shutdown")


app = FastAPI(title="Conflict Detection Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(conflicts_router, prefix="/conflicts", tags=["conflicts"])
health_router = create_health_router("conflict_detection", [])
app.include_router(health_router)
