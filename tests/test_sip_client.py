"""Integration tests for SIPClient against a scripted fake SIP server."""

import asyncio
import os
import tempfile

import pytest

os.environ.setdefault("SIPRING_DATA_DIR", tempfile.mkdtemp())

from sipring.sip.client import SIPClient, CallResult
from tests.fake_sip import FakeSIPServer, sip_response, wait_until


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


async def test_foreign_call_id_responses_are_ignored(fake_server):
    """A stale 486 for another Call-ID must not kill the current call."""

    def handler(msg):
        if msg.startswith("INVITE "):
            return [
                sip_response(msg, 486, "Busy Here", to_tag="old",
                             cseq="1 INVITE", call_id="sipring-stale123"),
                sip_response(msg, 180, "Ringing"),
            ]
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

    # Without filtering, the stale 486 would produce BUSY.
    assert result == CallResult.COMPLETED


async def test_invite_is_retransmitted_until_response(fake_server):
    """Lost INVITEs must be retransmitted; the third attempt gets through."""
    state = {"invites": 0}

    def handler(msg):
        if msg.startswith("INVITE "):
            state["invites"] += 1
            if state["invites"] < 3:
                return []  # simulate packet loss
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
    result = await client.ring(duration=0.2)

    assert result == CallResult.COMPLETED
    assert len(fake_server.requests("INVITE")) >= 3


async def test_no_retransmission_after_provisional_response(fake_server):
    """A 100 Trying must stop retransmissions even before 180 arrives."""

    def handler(msg):
        if msg.startswith("INVITE "):
            return [sip_response(msg, 100, "Trying")]
        if msg.startswith("CANCEL "):
            return [
                sip_response(msg, 200, "OK"),
                sip_response(msg, 487, "Request Terminated",
                             to_tag="gig1", cseq="1 INVITE"),
            ]
        return []

    fake_server.handler = handler
    client = make_client(fake_server.port, invite_retransmit_interval=0.05)

    async def run():
        return await client.ring(duration=0.2)

    task = asyncio.create_task(run())
    await asyncio.sleep(0.5)
    client.request_cancel()
    result = await task

    assert result in (CallResult.CANCELLED, CallResult.TIMEOUT)
    assert len(fake_server.requests("INVITE")) == 1


def _branch_of(message: str) -> str:
    import re
    return re.search(r"branch=(\S+)", message).group(1)


async def test_busy_response_is_acked(fake_server):
    """486 Busy must be ACKed with the INVITE's branch."""

    def handler(msg):
        if msg.startswith("INVITE "):
            return [sip_response(msg, 486, "Busy Here",
                                 to_tag="gig1", cseq="1 INVITE")]
        return []

    fake_server.handler = handler
    client = make_client(fake_server.port)
    result = await client.ring(duration=0.2)

    assert result == CallResult.BUSY
    assert await wait_until(lambda: len(fake_server.requests("ACK")) == 1)
    acks = fake_server.requests("ACK")
    assert _branch_of(acks[0]) == _branch_of(fake_server.requests("INVITE")[0])
    assert "CSeq: 1 ACK" in acks[0]


async def test_487_after_cancel_is_acked(fake_server):
    """The 487 that terminates a cancelled INVITE must be ACKed."""

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
    result = await client.ring(duration=0.2)

    assert result == CallResult.COMPLETED
    assert await wait_until(lambda: len(fake_server.requests("ACK")) == 1)
