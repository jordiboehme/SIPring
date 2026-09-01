"""Integration tests for SIPClient against a scripted fake SIP server."""

import asyncio
import os
import tempfile

import pytest

os.environ.setdefault("SIPRING_DATA_DIR", tempfile.mkdtemp())

from sipring.sip.client import SIPClient, CallResult
from tests.fake_sip import FakeSIPServer, sip_response


@pytest.fixture
async def fake_server():
    loop = asyncio.get_event_loop()
    transport, server = await loop.create_datagram_endpoint(
        FakeSIPServer, local_addr=("127.0.0.1", 0)
    )
    yield server
    transport.close()


def make_client(port: int, **kwargs) -> SIPClient:
    kwargs.setdefault("invite_retransmit_interval", 0.05)
    return SIPClient(
        target_user="**610",
        target_host="127.0.0.1",
        target_port=port,
        caller_name="Test",
        caller_user="107",
        local_port=0,
        **kwargs,
    )


async def test_ring_rings_and_cancels_cleanly(fake_server):
    """Happy path: INVITE -> 180, duration elapses -> CANCEL -> 200 + 487."""

    def handler(msg):
        if msg.startswith("INVITE "):
            return [sip_response(msg, 180, "Ringing")]
        if msg.startswith("CANCEL "):
            return [
                sip_response(msg, 200, "OK"),
                sip_response(msg, 487, "Request Terminated",
                             to_tag="gig1", cseq="1 INVITE"),
            ]
        return []

    fake_server.handler = handler
    client = make_client(fake_server.port)
    result = await client.ring(duration=0.3)

    assert result == CallResult.COMPLETED
    assert len(fake_server.requests("CANCEL")) >= 1
