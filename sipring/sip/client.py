"""Async SIP client for making ring calls."""

import asyncio
import logging
import socket
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable

from ..config import get_settings
from .messages import (
    SIPMessage,
    CallState,
    generate_call_id,
    generate_branch,
    generate_tag,
    parse_response_code,
    parse_to_tag,
)

logger = logging.getLogger(__name__)


class CallResult(str, Enum):
    """Result of a ring attempt."""
    CANCELLED = "cancelled"
    ANSWERED = "answered"
    TIMEOUT = "timeout"
    ERROR = "error"
    BUSY = "busy"


_local_ip_cache: dict[tuple[str, int], str] = {}


def get_local_ip(target_host: str, target_port: int) -> str:
    """Determine local IP address that can reach the target (cached)."""
    key = (target_host, target_port)
    cached = _local_ip_cache.get(key)
    if cached is not None:
        return cached
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((target_host, target_port))
        ip = sock.getsockname()[0]
    finally:
        sock.close()
    _local_ip_cache[key] = ip
    return ip


class SIPProtocol(asyncio.DatagramProtocol):
    """Async UDP protocol for SIP messages."""

    def __init__(self):
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.response_queue: asyncio.Queue[str] = asyncio.Queue()
        self._closed = asyncio.Event()

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            response = data.decode('utf-8')
            self.response_queue.put_nowait(response)
        except Exception as e:
            logger.warning(f"Failed to decode SIP response: {e}")

    def error_received(self, exc: Exception) -> None:
        logger.error(f"UDP error: {exc}")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        self._closed.set()

    def send(self, message: str, addr: tuple) -> None:
        if self.transport:
            self.transport.sendto(message.encode('utf-8'), addr)


class SIPClient:
    """Async SIP client for making ring calls."""

    def __init__(
        self,
        target_user: str,
        target_host: str,
        target_port: int = 5060,
        caller_name: str = "SIPring",
        caller_user: str = "sipring",
        local_host: str = "",
        local_port: int = 5062,
        user_agent: str = "SIPring",
    ):
        self.target_user = target_user
        self.target_host = target_host
        self.target_port = target_port
        self.caller_name = caller_name
        self.caller_user = caller_user
        self.local_port = local_port
        self.user_agent = user_agent

        # Determine local host: config override > parameter > auto-detect
        settings = get_settings()
        if settings.sip_host:
            # External host configured (NAT/proxy setup)
            # Advertise configured host in SIP headers, but bind to all interfaces
            self.local_host = settings.sip_host
            self._bind_host = "0.0.0.0"
        elif local_host:
            self.local_host = local_host
            self._bind_host = local_host
        else:
            self.local_host = get_local_ip(target_host, target_port)
            self._bind_host = self.local_host

        self._msg_builder: Optional[SIPMessage] = None
        self._protocol: Optional[SIPProtocol] = None
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._state = CallState()
        self._cancel_requested = False

    @property
    def state(self) -> str:
        """Current call state."""
        return self._state.state

    async def _connect(self) -> None:
        """Initialize UDP transport."""
        self._msg_builder = SIPMessage(
            target_user=self.target_user,
            target_host=self.target_host,
            target_port=self.target_port,
            caller_name=self.caller_name,
            caller_user=self.caller_user,
            local_host=self.local_host,
            local_port=self.local_port,
            user_agent=self.user_agent,
        )

        loop = asyncio.get_event_loop()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            SIPProtocol,
            local_addr=(self._bind_host, self.local_port),
        )
        logger.info(f"SIP client bound to {self._bind_host}:{self.local_port}, advertising {self.local_host}:{self.local_port}")

    async def _close(self) -> None:
        """Close transport."""
        if self._transport:
            self._transport.close()
            self._transport = None
            self._protocol = None

    def _send(self, message: str) -> None:
        """Send SIP message."""
        if self._protocol:
            self._protocol.send(message, (self.target_host, self.target_port))
            method = message.split()[0]
            logger.debug(f"Sent {method} to {self.target_host}:{self.target_port}")

    async def _receive(self, timeout: float = 5.0) -> Optional[str]:
        """Receive SIP response."""
        if not self._protocol:
            return None
        try:
            response = await asyncio.wait_for(
                self._protocol.response_queue.get(),
                timeout=timeout,
            )
            code = parse_response_code(response)
            logger.debug(f"Received {code}")
            return response
        except asyncio.TimeoutError:
            return None

    async def _send_invite(self) -> bool:
        """Send INVITE and wait for provisional response."""
        self._state.call_id = generate_call_id()
        self._state.from_tag = generate_tag()
        self._state.branch = generate_branch()
        self._state.cseq = 1
        self._state.state = "INVITING"

        message = self._msg_builder.build_invite(self._state)
        self._send(message)

        deadline = asyncio.get_event_loop().time() + 10.0
        while asyncio.get_event_loop().time() < deadline:
            if self._cancel_requested:
                return False

            response = await self._receive(timeout=1.0)
            if response:
                code = parse_response_code(response)
                if code == 100:
                    logger.debug("Got 100 Trying")
                    continue
                elif code in (180, 183):
                    logger.info(f"Got {code} - Phone is ringing")
                    self._state.state = "RINGING"
                    return True
                elif code == 200:
                    logger.info("Got 200 OK - Call answered during invite")
                    self._state.to_tag = parse_to_tag(response) or ""
                    self._state.state = "ANSWERED"
                    return True
                elif code == 486 or code == 600:
                    logger.info(f"Got {code} - Busy")
                    self._state.state = "TERMINATED"
                    return False
                elif code >= 400:
                    logger.warning(f"Error response: {code}")
                    self._state.state = "TERMINATED"
                    return False

        logger.warning("Timeout waiting for response")
        self._state.state = "TERMINATED"
        return False

    async def _send_cancel(self) -> bool:
        """Send CANCEL to stop ringing."""
        if self._state.state not in ("INVITING", "RINGING"):
            logger.warning(f"Cannot cancel in state {self._state.state}")
            return False

        self._state.state = "CANCELING"
        message = self._msg_builder.build_cancel(self._state)
        self._send(message)

        deadline = asyncio.get_event_loop().time() + 5.0
        got_200 = False
        got_487 = False

        while asyncio.get_event_loop().time() < deadline and not (got_200 and got_487):
            response = await self._receive(timeout=1.0)
            if response:
                code = parse_response_code(response)
                if code == 200 and "CANCEL" in response:
                    logger.debug("Got 200 OK for CANCEL")
                    got_200 = True
                elif code == 487:
                    logger.debug("Got 487 Request Terminated")
                    got_487 = True

        self._state.state = "TERMINATED"
        return got_200

    async def _send_bye(self) -> bool:
        """Send BYE to end answered call."""
        if self._state.state != "ANSWERED":
            logger.warning(f"Cannot send BYE in state {self._state.state}")
            return False

        if not self._state.to_tag:
            logger.warning("No To-tag, cannot send BYE")
            return False

        # Send ACK first
        ack_message = self._msg_builder.build_ack(self._state)
        self._send(ack_message)

        # Then BYE
        message = self._msg_builder.build_bye(self._state)
        self._send(message)

        deadline = asyncio.get_event_loop().time() + 5.0
        while asyncio.get_event_loop().time() < deadline:
            response = await self._receive(timeout=1.0)
            if response:
                code = parse_response_code(response)
                if code == 200:
                    logger.debug("Got 200 OK for BYE")
                    self._state.state = "TERMINATED"
                    return True

        self._state.state = "TERMINATED"
        return False

    def request_cancel(self) -> None:
        """Request cancellation of the current call."""
        self._cancel_requested = True

    async def ring(
        self,
        duration: float = 30.0,
        on_state_change: Optional[Callable[[str], None]] = None,
    ) -> CallResult:
        """
        Ring phone for specified duration.

        Args:
            duration: Maximum ring duration in seconds
            on_state_change: Optional callback for state changes

        Returns:
            CallResult enum value
        """
        self._cancel_requested = False
        self._state = CallState()

        def notify_state(state: str) -> None:
            if on_state_change:
                on_state_change(state)

        try:
            await self._connect()
            notify_state("CONNECTING")

            if not await self._send_invite():
                if self._cancel_requested:
                    await self._send_cancel()
                    return CallResult.CANCELLED
                return CallResult.ERROR

            if self._state.state == "ANSWERED":
                notify_state("ANSWERED")
                await self._send_bye()
                return CallResult.ANSWERED

            notify_state("RINGING")
            ring_end = asyncio.get_event_loop().time() + duration

            while asyncio.get_event_loop().time() < ring_end:
                if self._cancel_requested:
                    logger.info("Cancel requested")
                    break

                response = await self._receive(timeout=0.5)
                if response:
                    code = parse_response_code(response)
                    if code == 200:
                        logger.info("Call answered during ring")
                        self._state.to_tag = parse_to_tag(response) or ""
                        self._state.state = "ANSWERED"
                        notify_state("ANSWERED")
                        await self._send_bye()
                        return CallResult.ANSWERED

            notify_state("CANCELING")
            await self._send_cancel()
            return CallResult.CANCELLED

        except Exception as e:
            logger.exception(f"Ring error: {e}")
            return CallResult.ERROR
        finally:
            await self._close()
            notify_state("TERMINATED")
