import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.database import init_db, close_db
from .api.routes import router
from .api.websocket import ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting PULSE backend...")
    await init_db()
    # Start background scheduler (imported lazily to avoid circular imports)
    from .api.scheduler import start_scheduler
    start_scheduler()
    logger.info("PULSE ready")
    yield
    # Shutdown
    logger.info("Shutting down PULSE...")
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="PULSE API",
        version=settings.app_version,
        description="Personal Intelligence Operating System - API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api")
    app.include_router(ws_router)

    return app


app = create_app()
