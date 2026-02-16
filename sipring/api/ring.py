"""Ring trigger endpoints."""

import base64
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..config import get_settings
from ..models import RingEvent, RingResponse
from ..ring_manager import get_ring_manager
from ..storage import get_storage, ConfigNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ring"])


def _get_source_user(request: Request) -> Optional[str]:
    """Extract authenticated username from request, if any."""
    settings = get_settings()
    if not settings.auth_enabled:
        return None
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    try:
        scheme, credentials = auth.split()
        if scheme.lower() == "basic":
            decoded = base64.b64decode(credentials).decode("utf-8")
            username, _ = decoded.split(":", 1)
            return username
    except Exception:
        pass
    return None


@router.get("/ring/{id_or_slug}", response_model=RingResponse)
async def trigger_ring(
    id_or_slug: str,
    request: Request,
    duration: Optional[int] = Query(None, ge=1, le=300, description="Override ring duration"),
    wait: bool = Query(False, description="Wait for ring to complete"),
):
    """
    Trigger a ring for the specified configuration.

    - Use UUID or slug to identify the configuration
    - Optionally override the configured ring duration
    - Use wait=true to wait for the ring to complete
    """
    storage = get_storage()
    ring_manager = get_ring_manager()

    try:
        config = storage.get_config(id_or_slug)
    except ConfigNotFoundError:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {id_or_slug}")

    if not config.enabled:
        raise HTTPException(status_code=400, detail="Configuration is disabled")

    ring_duration = duration or config.ring_duration

    # Check if already ringing
    if ring_manager.is_active(config.id):
        return RingResponse(
            status="already_ringing",
            config_id=config.id,
            message=f"Ring already in progress for {config.name}",
        )

    # Build event
    event = RingEvent(
        config_id=config.id,
        config_name=config.name,
        config_slug=config.slug,
        duration=ring_duration,
        source_ip=request.client.host if request.client else None,
        source_user=_get_source_user(request),
        trigger_type="ring",
    )

    # Start the ring
    started = await ring_manager.start_ring(
        config_id=config.id,
        sip_user=config.sip_user,
        sip_server=config.sip_server,
        sip_port=config.sip_port,
        caller_name=config.caller_name,
        caller_user=config.caller_user,
        ring_duration=ring_duration,
        local_port=config.local_port,
        event=event,
    )

    if not started:
        raise HTTPException(status_code=500, detail="Failed to start ring")

    logger.info(f"Ring triggered for {config.name} (duration={ring_duration}s)")

    if wait:
        result = await ring_manager.wait_for_completion(config.id, timeout=ring_duration + 10)
        return RingResponse(
            status="completed",
            config_id=config.id,
            message=f"Ring completed for {config.name}",
            result=result.value if result else "unknown",
        )

    return RingResponse(
        status="started",
        config_id=config.id,
        message=f"Ring started for {config.name} (duration={ring_duration}s)",
    )


@router.get("/ring/{id_or_slug}/cancel", response_model=RingResponse)
async def cancel_ring(id_or_slug: str):
    """
    Cancel an active ring for the specified configuration.
    """
    storage = get_storage()
    ring_manager = get_ring_manager()

    try:
        config = storage.get_config(id_or_slug)
    except ConfigNotFoundError:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {id_or_slug}")

    cancelled = await ring_manager.cancel_ring(config.id)

    if not cancelled:
        return RingResponse(
            status="not_active",
            config_id=config.id,
            message=f"No active ring for {config.name}",
        )

    return RingResponse(
        status="cancelling",
        config_id=config.id,
        message=f"Cancelling ring for {config.name}",
    )


@router.get("/ring/{id_or_slug}/status", response_model=RingResponse)
async def ring_status(id_or_slug: str):
    """
    Get the current ring status for the specified configuration.
    """
    storage = get_storage()
    ring_manager = get_ring_manager()

    try:
        config = storage.get_config(id_or_slug)
    except ConfigNotFoundError:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {id_or_slug}")

    state = ring_manager.get_state(config.id)

    if state:
        return RingResponse(
            status="ringing",
            config_id=config.id,
            message=f"Ring in progress for {config.name}",
            result=state,
        )

    return RingResponse(
        status="idle",
        config_id=config.id,
        message=f"No active ring for {config.name}",
        result=config.last_ring_status,
    )
