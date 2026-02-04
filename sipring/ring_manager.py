"""Active call management."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from .sip.client import SIPClient, CallResult
from .storage import get_storage

logger = logging.getLogger(__name__)


@dataclass
class ActiveCall:
    """Tracks an active ring call."""
    config_id: UUID
    client: SIPClient
    task: asyncio.Task
    started_at: datetime = field(default_factory=datetime.utcnow)
    state: str = "starting"


class RingManager:
    """Manages active ring calls."""

    def __init__(self):
        self._active_calls: Dict[UUID, ActiveCall] = {}
        self._lock = asyncio.Lock()

    async def start_ring(
        self,
        config_id: UUID,
        sip_user: str,
        sip_server: str,
        sip_port: int,
        caller_name: str,
        caller_user: str,
        ring_duration: float,
        local_port: int,
    ) -> bool:
        """
        Start a ring call for a configuration.

        Returns False if a call is already active for this config.
        """
        async with self._lock:
            if config_id in self._active_calls:
                logger.warning(f"Ring already active for config {config_id}")
                return False

            client = SIPClient(
                target_user=sip_user,
                target_host=sip_server,
                target_port=sip_port,
                caller_name=caller_name,
                caller_user=caller_user,
                local_port=local_port,
            )

            # Create task for the ring
            task = asyncio.create_task(
                self._run_ring(config_id, client, ring_duration)
            )

            self._active_calls[config_id] = ActiveCall(
                config_id=config_id,
                client=client,
                task=task,
            )

            logger.info(f"Started ring for config {config_id}")
            return True

    async def _run_ring(
        self,
        config_id: UUID,
        client: SIPClient,
        duration: float,
    ) -> CallResult:
        """Execute ring and update status."""
        try:
            def on_state_change(state: str):
                if config_id in self._active_calls:
                    self._active_calls[config_id].state = state

            result = await client.ring(
                duration=duration,
                on_state_change=on_state_change,
            )

            # Update storage with result
            try:
                storage = get_storage()
                storage.update_ring_status(str(config_id), result.value)
            except Exception as e:
                logger.error(f"Failed to update ring status: {e}")

            return result

        finally:
            # Remove from active calls
            async with self._lock:
                self._active_calls.pop(config_id, None)
            logger.info(f"Ring completed for config {config_id}")

    async def cancel_ring(self, config_id: UUID) -> bool:
        """
        Cancel an active ring call.

        Returns True if call was found and cancelled.
        """
        async with self._lock:
            call = self._active_calls.get(config_id)
            if not call:
                logger.warning(f"No active ring for config {config_id}")
                return False

            call.client.request_cancel()
            logger.info(f"Cancellation requested for config {config_id}")
            return True

    def is_active(self, config_id: UUID) -> bool:
        """Check if a ring is active for the given config."""
        return config_id in self._active_calls

    def get_state(self, config_id: UUID) -> Optional[str]:
        """Get current state of a ring call."""
        call = self._active_calls.get(config_id)
        return call.state if call else None

    def get_active_calls(self) -> Dict[UUID, str]:
        """Get all active calls with their states."""
        return {
            call.config_id: call.state
            for call in self._active_calls.values()
        }

    async def wait_for_completion(self, config_id: UUID, timeout: float = 60.0) -> Optional[CallResult]:
        """Wait for a ring call to complete."""
        call = self._active_calls.get(config_id)
        if not call:
            return None

        try:
            return await asyncio.wait_for(call.task, timeout=timeout)
        except asyncio.TimeoutError:
            return None


# Global ring manager instance
_ring_manager: Optional[RingManager] = None


def get_ring_manager() -> RingManager:
    """Get ring manager instance."""
    global _ring_manager
    if _ring_manager is None:
        _ring_manager = RingManager()
    return _ring_manager
