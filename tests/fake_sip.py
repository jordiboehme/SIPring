"""Scripted fake SIP UDP server for client tests."""

import asyncio
import re
from typing import Callable, Optional, TypeVar, Awaitable

T = TypeVar("T")


class FakeSIPServer(asyncio.DatagramProtocol):
    """Records every SIP request and answers via a scriptable handler.

    Tests set `server.handler` to a function (request: str) -> list[str]
    returning raw SIP responses to send back to the client.
    """

    def __init__(self):
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.received: list[str] = []
        self.handler: Optional[Callable[[str], list[str]]] = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        msg = data.decode("utf-8")
        self.received.append(msg)
        if self.handler:
            for response in self.handler(msg):
                self.transport.sendto(response.encode("utf-8"), addr)

    @property
    def port(self) -> int:
        return self.transport.get_extra_info("sockname")[1]

    def requests(self, method: str) -> list[str]:
        """All received requests of a given SIP method (e.g. 'INVITE')."""
        return [m for m in self.received if m.startswith(f"{method} ")]


def _header(request: str, name: str) -> str:
    match = re.search(rf"^{name}:\s*(.+?)\r?$", request, re.IGNORECASE | re.MULTILINE)
    return match.group(1) if match else ""


def sip_response(
    request: str,
    code: int,
    reason: str,
    to_tag: Optional[str] = None,
    cseq: Optional[str] = None,
    call_id: Optional[str] = None,
) -> str:
    """Build a SIP response echoing the request's dialog headers.

    `cseq` overrides the echoed CSeq line (e.g. "1 INVITE" to answer the
    INVITE transaction while reacting to a CANCEL request). `call_id`
    overrides Call-ID to simulate stale/foreign responses.
    """
    to = _header(request, "To")
    if to_tag:
        to = f"{to};tag={to_tag}"
    return (
        f"SIP/2.0 {code} {reason}\r\n"
        f"Via: {_header(request, 'Via')}\r\n"
        f"From: {_header(request, 'From')}\r\n"
        f"To: {to}\r\n"
        f"Call-ID: {call_id or _header(request, 'Call-ID')}\r\n"
        f"CSeq: {cseq or _header(request, 'CSeq')}\r\n"
        f"Content-Length: 0\r\n"
        f"\r\n"
    )


async def wait_until(predicate: Callable[[], T], timeout: float = 1.0) -> T:
    """Poll until predicate() is truthy or timeout elapses; returns predicate()."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while not predicate() and loop.time() < deadline:
        await asyncio.sleep(0.01)
    return predicate()
