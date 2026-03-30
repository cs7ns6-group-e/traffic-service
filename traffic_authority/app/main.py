import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.database import init_db
from shared.exceptions import register_exception_handlers
from shared.health import create_health_router
from shared.logging import setup_logging

from app.config import get_settings
from app.routes.authority import router as authority_router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.app_name, settings.debug)
    await init_db()
    logger.info("Traffic authority service started")
    yield
    logger.info("Traffic authority service shutdown")


app = FastAPI(title="Traffic Authority Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(authority_router, prefix="/authority", tags=["authority"])
health_router = create_health_router("traffic_authority", [])
app.include_router(health_router)
