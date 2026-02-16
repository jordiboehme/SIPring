"""Ring event log endpoints."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query

from ..models import RingEventResponse
from ..storage import get_event_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=RingEventResponse)
async def list_events(
    config_id: Optional[UUID] = Query(None, description="Filter by config ID"),
    since: Optional[datetime] = Query(None, description="Events after this time (ISO format)"),
    hours: Optional[int] = Query(None, ge=1, description="Shortcut: last N hours"),
    days: Optional[int] = Query(None, ge=1, description="Shortcut: last N days"),
    result: Optional[str] = Query(None, description="Filter by result"),
    trigger_type: Optional[str] = Query(None, description="Filter by trigger type"),
    limit: int = Query(50, ge=1, le=500, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """List ring events with filtering and pagination."""
    # Priority: since > hours > days
    if since is None:
        now = datetime.now(timezone.utc)
        if hours is not None:
            since = now - timedelta(hours=hours)
        elif days is not None:
            since = now - timedelta(days=days)

    event_storage = get_event_storage()
    events, total = event_storage.list_events(
        config_id=config_id,
        since=since,
        result=result,
        trigger_type=trigger_type,
        limit=limit,
        offset=offset,
    )

    return RingEventResponse(events=events, count=len(events), total=total)
