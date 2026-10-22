from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.auth import validate_security_configuration
from app.api.v1.api import api_router

# Configure basic logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
)
logger = logging.getLogger("vspl.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_security_configuration()
    logger.info(
        f"Starting {settings.PROJECT_NAME} in [{settings.ENVIRONMENT}] mode "
        f"(Costing baseline start date: {settings.COSTING_START_DATE})"
    )
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Production Material Management & Costing System for Vijay Spheroidals Pvt. Ltd. (VSPL). "
        "Engineered for SG iron foundry operations, tracking 741 material items, append-only "
        "inventory ledgers, heat log reconciliations, and weighted-average costing."
    ),
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
origins = settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
def root():
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")


@app.get("/health", include_in_schema=False)
def health_redirect():
    """Convenience redirect from /health to /api/v1/health."""
    return RedirectResponse(url=f"{settings.API_V1_STR}/health")
