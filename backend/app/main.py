from contextlib import asynccontextmanager
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

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


# Interactive documentation exposes the full API surface; it is off in production unless explicitly enabled.
_docs_enabled = settings.ENABLE_API_DOCS if settings.ENABLE_API_DOCS is not None else settings.ENVIRONMENT != "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Production Material Management & Costing System for Vijay Spheroidals Pvt. Ltd. (VSPL). "
        "Engineered for SG iron foundry operations, tracking 741 material items, append-only "
        "inventory ledgers, heat log reconciliations, and weighted-average costing."
    ),
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if _docs_enabled else None,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    lifespan=lifespan,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Baseline response hardening: no content sniffing or framing, no caching of API data, HSTS in production."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith(settings.API_V1_STR):
        response.headers.setdefault("Cache-Control", "no-store")
    if settings.ENVIRONMENT == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

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


_frontend_dist = Path(settings.FRONTEND_DIST_DIR).resolve() if settings.FRONTEND_DIST_DIR else None
_serve_frontend = bool(_frontend_dist and (_frontend_dist / "index.html").is_file())

if not _serve_frontend:

    @app.get("/", include_in_schema=False)
    def root():
        """Redirect root path to interactive Swagger documentation."""
        return RedirectResponse(url="/docs")


@app.get("/health", include_in_schema=False)
def health_redirect():
    """Convenience redirect from /health to /api/v1/health."""
    return RedirectResponse(url=f"{settings.API_V1_STR}/health")


if _serve_frontend:

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        """Serve the built single-page frontend. Unknown /api paths stay 404; files outside the folder are refused."""
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        if full_path:
            candidate = (_frontend_dist / full_path).resolve()
            if candidate.is_file() and _frontend_dist in candidate.parents:
                return FileResponse(candidate)
        return FileResponse(_frontend_dist / "index.html")
