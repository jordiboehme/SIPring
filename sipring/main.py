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
from .api import ring_router, config_router, events_router
from .storage import get_storage, get_event_storage
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
    get_event_storage().prune_events()
    yield
    logger.info("SIPring shutting down")


# Create FastAPI app
app = FastAPI(
    title="SIPring",
    description="SIP phone ringing service for triggering alerts via HTTP",
    version="0.2.1",
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
app.include_router(events_router)

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


RESULT_BADGE_MAP = {
    "cancelled": "badge-warning",
    "answered": "badge-success",
    "timeout": "badge-info",
    "error": "badge-error",
    "busy": "badge-warning",
}


@app.get("/events", response_class=HTMLResponse)
async def events_page(
    request: Request,
    config_id: str = None,
    range: str = "7d",
    result: str = None,
    trigger_type: str = None,
    limit: int = 50,
    offset: int = 0,
    _: bool = Depends(optional_auth),
):
    """Event log page."""
    from datetime import datetime, timedelta, timezone
    from uuid import UUID as _UUID

    now = datetime.now(timezone.utc)
    since = None
    if range == "24h":
        since = now - timedelta(hours=24)
    elif range == "7d":
        since = now - timedelta(days=7)
    elif range == "30d":
        since = now - timedelta(days=30)

    parsed_config_id = None
    if config_id:
        try:
            parsed_config_id = _UUID(config_id)
        except ValueError:
            pass

    event_storage = get_event_storage()
    events, total = event_storage.list_events(
        config_id=parsed_config_id,
        since=since,
        result=result or None,
        trigger_type=trigger_type or None,
        limit=limit,
        offset=offset,
    )

    storage = get_storage()
    configs = storage.list_configs()

    return templates.TemplateResponse(
        request, "events.html", {
            "events": events,
            "total": total,
            "limit": limit,
            "offset": offset,
            "configs": configs,
            "filter_range": range,
            "filter_config_id": config_id or "",
            "filter_result": result or "",
            "filter_trigger_type": trigger_type or "",
            "result_badge_map": RESULT_BADGE_MAP,
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


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, _: bool = Depends(optional_auth)):
    """About page with version, license, and credits."""
    from datetime import datetime
    return templates.TemplateResponse(
        request, "about.html", {
            "version": app.version,
            "year": datetime.now().year,
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
