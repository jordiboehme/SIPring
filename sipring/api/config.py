"""Configuration CRUD endpoints."""

import base64
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from ..config import get_settings
from ..models import (
    RingConfig,
    RingConfigCreate,
    RingConfigUpdate,
    RingConfigResponse,
    RingEvent,
    RingResponse,
    ConfigListResponse,
)
from ..ring_manager import get_ring_manager
from ..storage import get_storage, ConfigNotFoundError, StorageError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/configs", tags=["config"])


def config_to_response(config: RingConfig, request: Request) -> RingConfigResponse:
    """Convert RingConfig to response with URLs."""
    settings = get_settings()
    base_url = settings.get_base_url(str(request.base_url))
    identifier = config.slug or str(config.id)

    return RingConfigResponse(
        **config.model_dump(),
        ring_url=f"{base_url}/ring/{identifier}",
        cancel_url=f"{base_url}/ring/{identifier}/cancel",
    )


@router.get("", response_model=ConfigListResponse)
async def list_configs(request: Request):
    """List all ring configurations."""
    storage = get_storage()
    configs = storage.list_configs()

    return ConfigListResponse(
        configs=[config_to_response(c, request) for c in configs],
        count=len(configs),
    )


@router.post("", response_model=RingConfigResponse, status_code=201)
async def create_config(config_data: RingConfigCreate, request: Request):
    """Create a new ring configuration."""
    storage = get_storage()

    try:
        config = storage.create_config(config_data)
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(f"Created config: {config.id} ({config.name})")
    return config_to_response(config, request)


@router.get("/{id_or_slug}", response_model=RingConfigResponse)
async def get_config(id_or_slug: str, request: Request):
    """Get a ring configuration by UUID or slug."""
    storage = get_storage()

    try:
        config = storage.get_config(id_or_slug)
    except ConfigNotFoundError:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {id_or_slug}")

    return config_to_response(config, request)


@router.put("/{id_or_slug}", response_model=RingConfigResponse)
async def update_config(id_or_slug: str, update_data: RingConfigUpdate, request: Request):
    """Update a ring configuration."""
    storage = get_storage()

    try:
        config = storage.update_config(id_or_slug, update_data)
    except ConfigNotFoundError:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {id_or_slug}")
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(f"Updated config: {config.id}")
    return config_to_response(config, request)


@router.delete("/{id_or_slug}", status_code=204)
async def delete_config(id_or_slug: str):
    """Delete a ring configuration."""
    storage = get_storage()
    ring_manager = get_ring_manager()

    try:
        config = storage.get_config(id_or_slug)
    except ConfigNotFoundError:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {id_or_slug}")

    # Cancel any active ring
    if ring_manager.is_active(config.id):
        await ring_manager.cancel_ring(config.id)

    storage.delete_config(id_or_slug)
    logger.info(f"Deleted config: {config.id}")


@router.post("/{id_or_slug}/clone", response_model=RingConfigResponse, status_code=201)
async def clone_config(id_or_slug: str, request: Request):
    """
    Clone an existing ring configuration.

    Creates a copy with a new UUID and modified name/slug.
    """
    storage = get_storage()

    try:
        config = storage.get_config(id_or_slug)
    except ConfigNotFoundError:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {id_or_slug}")

    # Create clone data with modified name and slug
    clone_data = RingConfigCreate(
        name=f"{config.name} (Copy)",
        slug=f"{config.slug}-copy" if config.slug else None,
        sip_user=config.sip_user,
        sip_server=config.sip_server,
        sip_port=config.sip_port,
        caller_name=config.caller_name,
        caller_user=config.caller_user,
        ring_duration=config.ring_duration,
        local_port=config.local_port,
        enabled=config.enabled,
    )

    try:
        new_config = storage.create_config(clone_data)
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(f"Cloned config {config.id} to {new_config.id}")
    return config_to_response(new_config, request)


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


@router.post("/{id_or_slug}/test", response_model=RingResponse)
async def test_config(id_or_slug: str, request: Request, duration: int = 3):
    """
    Test a ring configuration with a short ring.

    Default duration is 3 seconds.
    """
    storage = get_storage()
    ring_manager = get_ring_manager()

    try:
        config = storage.get_config(id_or_slug)
    except ConfigNotFoundError:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {id_or_slug}")

    if ring_manager.is_active(config.id):
        return RingResponse(
            status="already_ringing",
            config_id=config.id,
            message=f"Ring already in progress for {config.name}",
        )

    # Limit test duration
    test_duration = min(duration, 10)

    event = RingEvent(
        config_id=config.id,
        config_name=config.name,
        config_slug=config.slug,
        duration=test_duration,
        source_ip=request.client.host if request.client else None,
        source_user=_get_source_user(request),
        trigger_type="test",
    )

    started = await ring_manager.start_ring(
        config_id=config.id,
        sip_user=config.sip_user,
        sip_server=config.sip_server,
        sip_port=config.sip_port,
        caller_name=config.caller_name,
        caller_user=config.caller_user,
        ring_duration=test_duration,
        local_port=config.local_port,
        event=event,
    )

    if not started:
        raise HTTPException(status_code=500, detail="Failed to start test ring")

    # Wait for completion
    result = await ring_manager.wait_for_completion(config.id, timeout=test_duration + 10)

    return RingResponse(
        status="completed",
        config_id=config.id,
        message=f"Test ring completed for {config.name}",
        result=result.value if result else "unknown",
    )
