import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.datasets import router as datasets_router

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(f"Starting up {settings.APP_NAME}...")
    
    # -----------------------------------------------------------------------
    # Recover stale background training jobs that were interrupted by restart
    # -----------------------------------------------------------------------
    from sqlalchemy import update
    from app.database import AsyncSessionLocal
    from app.models.trained_model import TrainedModel
    
    try:
        async with AsyncSessionLocal() as db:
            stmt = (
                update(TrainedModel)
                .where(TrainedModel.status.in_(["PENDING", "RUNNING"]))
                .values(
                    status="FAILED",
                    error_message="Training interrupted by server restart"
                )
                .execution_options(synchronize_session=False)
            )
            result = await db.execute(stmt)
            await db.commit()
            if result.rowcount > 0:
                logger.info(f"Recovered {result.rowcount} interrupted model training record(s).")
    except Exception as e:
        logger.exception("Failed to recover stale model training records on startup. Continuing startup...")
        
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

# CORS configuration
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(datasets_router, prefix=settings.API_V1_PREFIX)

