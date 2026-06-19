from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.logging import setup_logging
from app.scheduler.setup import setup_scheduler, shutdown_scheduler
from app.services.connections.http_client import close_coingecko_client
from app.api.coins import router as coins_router
from app.services.connections.mongodb import setup_indexes
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limiter import limiter
from app.api.auth import router as auth_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await setup_indexes()
    setup_scheduler()
    yield
    shutdown_scheduler()
    await close_coingecko_client()

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(coins_router)
app.include_router(auth_router)

@app.get("/")
async def root():
    return { "message": "Gecko API is running" }

