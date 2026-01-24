"""FastAPI application entry point."""

import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .api import ring_router, config_router
from .storage import get_storage
from .ring_manager import get_ring_manager

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    logger.info(f"SIPring starting, data dir: {settings.data_dir}")
    get_storage()
    yield
    logger.info("SIPring shutting down")


# Create FastAPI app
app = FastAPI(
    title="SIPring",
    description="SIP phone ringing service for triggering alerts via HTTP",
    version="0.1.0",
    lifespan=lifespan,
)

# Setup templates and static files
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

if (BASE_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include API routers
app.include_router(ring_router)
app.include_router(config_router)

# Basic auth setup
security = HTTPBasic()


def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify basic authentication if enabled."""
    if not settings.auth_enabled:
        return True

    correct_username = secrets.compare_digest(
        credentials.username.encode("utf8"),
        settings.username.encode("utf8"),
    )
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf8"),
        settings.password.encode("utf8"),
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


def optional_auth(request: Request):
    """Optional auth check - only for web UI routes."""
    if not settings.auth_enabled:
        return True

    auth = request.headers.get("Authorization")
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    # Parse basic auth
    try:
        scheme, credentials = auth.split()
        if scheme.lower() != "basic":
            raise HTTPException(status_code=401, detail="Invalid auth scheme")

        import base64
        decoded = base64.b64decode(credentials).decode("utf-8")
        username, password = decoded.split(":", 1)

        correct_username = secrets.compare_digest(username, settings.username)
        correct_password = secrets.compare_digest(password, settings.password)

        if not (correct_username and correct_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return True


# Web UI routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, _: bool = Depends(optional_auth)):
    """Main dashboard showing all ring configurations."""
    storage = get_storage()
    ring_manager = get_ring_manager()

    configs = storage.list_configs()
    active_calls = ring_manager.get_active_calls()

    # Add ring status to configs
    config_data = []
    base_url = settings.get_base_url(str(request.base_url))
    for config in configs:
        identifier = config.slug or str(config.id)

        config_data.append({
            "config": config,
            "ring_url": f"{base_url}/ring/{identifier}",
            "cancel_url": f"{base_url}/ring/{identifier}/cancel",
            "is_ringing": config.id in active_calls,
            "ring_state": active_calls.get(config.id),
        })

    return templates.TemplateResponse(
        request, "dashboard.html", {
            "configs": config_data,
            "active_count": len(active_calls),
        }
    )


@app.get("/config/new", response_class=HTMLResponse)
async def new_config_form(request: Request, _: bool = Depends(optional_auth)):
    """Form to create a new configuration."""
    return templates.TemplateResponse(
        request, "config_form.html", {
            "config": None,
            "action": "Create",
        }
    )


@app.get("/config/{id_or_slug}/edit", response_class=HTMLResponse)
async def edit_config_form(request: Request, id_or_slug: str, _: bool = Depends(optional_auth)):
    """Form to edit an existing configuration."""
    storage = get_storage()

    try:
        config = storage.get_config(id_or_slug)
    except Exception:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return templates.TemplateResponse(
        request, "config_form.html", {
            "config": config,
            "action": "Update",
        }
    )


@app.get("/config/{id_or_slug}", response_class=HTMLResponse)
async def config_detail(request: Request, id_or_slug: str, _: bool = Depends(optional_auth)):
    """Detail view for a configuration."""
    storage = get_storage()
    ring_manager = get_ring_manager()

    try:
        config = storage.get_config(id_or_slug)
    except Exception:
        raise HTTPException(status_code=404, detail="Configuration not found")

    base_url = settings.get_base_url(str(request.base_url))
    identifier = config.slug or str(config.id)

    return templates.TemplateResponse(
        request, "config_detail.html", {
            "config": config,
            "ring_url": f"{base_url}/ring/{identifier}",
            "cancel_url": f"{base_url}/ring/{identifier}/cancel",
            "is_ringing": ring_manager.is_active(config.id),
            "ring_state": ring_manager.get_state(config.id),
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
