import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api.v1 import (
    health as health_v1,
    auth as auth_v1,
    readings as readings_v1,
    rules as rules_v1,
    alerts as alerts_v1,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s", "level":"%(levelname)s", "logger":"%(name)s", "message":"%(message)s"}'
)
logger = logging.getLogger("campuspulse.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing CampusPulse database schema...")
    await init_db()
    logger.info("CampusPulse database initialized.")
    yield
    logger.info("CampusPulse shutting down...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="CampusPulse: Real-Time Campus Sensor Monitoring and Alert Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID Middleware
@app.middleware("http")
async def add_request_id_and_timing(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


# Register API v1 routers
app.include_router(health_v1.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_v1.router, prefix=settings.API_V1_PREFIX)
app.include_router(readings_v1.router, prefix=settings.API_V1_PREFIX)
app.include_router(rules_v1.router, prefix=settings.API_V1_PREFIX)
app.include_router(alerts_v1.router, prefix=settings.API_V1_PREFIX)

# Also expose /health/live and /health/ready at root for container orchestrators
app.include_router(health_v1.router, prefix="")
