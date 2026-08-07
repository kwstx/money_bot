import logging
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.config import settings
from src.publisher import publisher
from src.api import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting FOMO Listener Microservice")
    await publisher.connect()
    yield
    # Shutdown logic
    logger.info("Shutting down FOMO Listener Microservice")
    await publisher.disconnect()

app = FastAPI(
    title="FOMO Listener",
    description="Microservice to ingest events and publish to a message broker.",
    version="1.0.0",
    lifespan=lifespan
)

# Include the API router
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
