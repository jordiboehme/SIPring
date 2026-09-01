# Ring Robustness and UI Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the SIP ring path robust against packet loss, stale retransmissions, and race conditions; protect the API with basic auth; make the web UI live-updating and error-honest.

**Architecture:** All SIP protocol fixes live in `sipring/sip/client.py` and `sipring/sip/messages.py`, tested against a scripted fake SIP UDP server (`tests/fake_sip.py`). Auth moves to a new `sipring/security.py` used by both the API routers and the web UI routes. UI changes are template + `main.js` edits plus one new authenticated status endpoint for polling.

**Tech Stack:** Python 3.10+, FastAPI 0.141.1, asyncio DatagramProtocol, pytest 9.1.1 + pytest-asyncio (auto mode), vanilla JS, Jinja2 templates.

**Spec:** The review findings in the 2026-09-01 session (summarized below). No separate spec doc exists.

## Spec summary (what is being fixed and why)

- **Part 2.1:** INVITE is sent once over UDP; one lost packet = phone never rings. Add RFC 3261 Timer-A-style retransmission (interval doubling) until the first response.
- **Part 2.2:** Non-2xx final responses (486, 487, 4xx) are never ACKed, so the Gigaset retransmits them for ~30s; those stale packets can poison the next call's transaction. Send ACK (same branch as INVITE per RFC 3261 17.1.1.3).
- **Part 2.3:** Any UDP packet on the local port is treated as a response for the current call. Filter received responses by Call-ID.
- **Part 2.4:** If the phone is answered between the cancel decision and the 487, the 200 OK to INVITE is ignored and the call is left hanging. Handle it: ACK + BYE, return `ANSWERED`.
- **Part 2.6:** Replace deprecated `datetime.utcnow` in `ring_manager.py`; replace the dead `verify_auth`/duplicated auth code with a `sipring/security.py` module; require basic auth (when configured) on `/api/*` while **`/ring/*` stays open intentionally** (user decision, 2026-09-01); fix CLAUDE.md's reference to the deleted `invite_haustuer_clean.sip`.
- **Part 2.7:** The INVITE has blank lines mid-headers (technically everything after the first `\r\n\r\n` is body). Rebuild as one RFC-compliant header block. Needs a manual Gigaset test before release (caller ID display risk).
- **Part 3.1/3.2:** Dashboard/detail ring state is a page-load snapshot and dashboard has no Cancel. Add a polled `/api/active-rings` endpoint, live badge updates, and dynamic Cancel buttons.
- **Part 3.3:** `triggerRing`/`testRing` never check `response.ok`, showing success toasts on errors. Fix.
- **Part 3.4:** Inline `onclick="deleteConfig('{{ name }}')"` breaks on quotes in config names. Move to `data-*` attributes + event delegation.
- **Part 3.5:** Inter font loads from Google Fonts; self-host it in `/static/fonts`.
- **Part 3.6:** `showToast` uses `innerHTML` for messages (use DOM APIs/`textContent`); `main.js` has a duplicated "Active Nav Item" section.

## Global Constraints

- Version stays **0.3.9** (already bumped and committed). Do NOT push or create a GitHub release; that happens only after Jordi's explicit go, following `crystalline://jordi/reference/release-and-release-notes-convention`.
- Commit messages: plain imperative sentences matching repo history (e.g. "Fix float duration in API endpoints"). **NO AI attribution of any kind** (no Co-Authored-By, no "Generated with" lines).
- User-facing text (UI strings, README, release notes): never use an em-dash "—"; use a plain hyphen "-". Oxford comma is fine.
- `/ring/*` and `/health` endpoints remain unauthenticated by design. Never add auth there.
- Python `>=3.10` (no 3.12-only syntax). Use `datetime.now(timezone.utc)` / `models.utc_now`, never `datetime.utcnow()`.
- Run tests with `.venv/bin/python -m pytest` from the repo root (`/Users/jordi/git/SIPring`). pytest-asyncio is in auto mode; `async def` tests need no marker.
- All SIP timing in tests must use short durations (`invite_retransmit_interval=0.05`, `duration<=0.5`) so the suite stays under ~10s.

## File Structure

- Create: `tests/fake_sip.py` - scripted fake SIP UDP server + response builder for tests
- Create: `tests/test_sip_client.py` - async integration tests for `SIPClient` against the fake server
- Create: `sipring/security.py` - basic-auth helpers (`require_auth`, `get_source_user`)
- Create: `tests/test_auth.py` - auth-enabled API tests
- Create: `sipring/static/fonts/` - self-hosted Inter woff2 files
- Modify: `sipring/sip/messages.py` - RFC INVITE, `build_ack_for_error`, `parse_call_id`, `parse_cseq_method`
- Modify: `sipring/sip/client.py` - retransmission, Call-ID filter, error ACKs, answered-during-cancel
- Modify: `sipring/ring_manager.py` - timezone-aware `started_at`
- Modify: `sipring/api/ring.py` - `active-rings` status router, use `security.get_source_user`
- Modify: `sipring/api/config.py`, `sipring/api/events.py` - router-level auth dependency
- Modify: `sipring/main.py` - use `security.require_auth`, drop dead auth code, register status router
- Modify: `sipring/static/js/main.js`, `sipring/templates/*.html`, `sipring/static/css/main.css`
- Modify: `CLAUDE.md`, `README.md`

---

### Task 1: Fake SIP server test harness + baseline happy-path test

**Files:**
- Create: `tests/fake_sip.py`
- Create: `tests/test_sip_client.py`

**Interfaces:**
- Produces: `FakeSIPServer` (attributes `received: list[str]`, `handler: Callable[[str], list[str]] | None`, property `port: int`, methods `requests(method: str) -> list[str]`), `sip_response(request, code, reason, to_tag=None, cseq=None) -> str`, pytest fixture `fake_server`, helper `make_client(port, **kwargs) -> SIPClient`. Tasks 2-6 use exactly these.

- [ ] **Step 1: Write the fake server module**

Create `tests/fake_sip.py`:

```python
"""Scripted fake SIP UDP server for client tests."""

import asyncio
import re
from typing import Callable, Optional


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
```

- [ ] **Step 2: Write the test file with fixture, helper, and the baseline test**

Create `tests/test_sip_client.py`:

```python
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
```

Note: `make_client` already passes `invite_retransmit_interval=0.05`; the parameter does not exist yet. To keep this task self-contained, add the parameter now as a no-op:

In `sipring/sip/client.py`, add to `SIPClient.__init__` signature after `user_agent: str = "SIPring"`:

```python
        invite_retransmit_interval: float = 0.5,
```

and in the body, next to `self.user_agent = user_agent`:

```python
        self.invite_retransmit_interval = invite_retransmit_interval
```

- [ ] **Step 3: Run the new test**

Run: `.venv/bin/python -m pytest tests/test_sip_client.py -v`
Expected: PASS (this is harness validation; current client code already handles the happy path).

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (36 existing + 1 new).

- [ ] **Step 5: Commit**

```bash
git add tests/fake_sip.py tests/test_sip_client.py sipring/sip/client.py
git commit -m "Add fake SIP server test harness and baseline ring test"
```

---

### Task 2: Filter received responses by Call-ID

**Files:**
- Modify: `sipring/sip/messages.py` (add `parse_call_id`)
- Modify: `sipring/sip/client.py` (`_receive`)
- Test: `tests/test_sip_client.py`, `tests/test_messages.py`

**Interfaces:**
- Consumes: `fake_server` fixture, `make_client`, `sip_response` from Task 1.
- Produces: `parse_call_id(response: str) -> Optional[str]` in `sipring/sip/messages.py`. `SIPClient._receive` drops responses whose Call-ID does not match `self._state.call_id`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_messages.py`:

```python
def test_parse_call_id():
    """Test Call-ID extraction from a response."""
    from sipring.sip.messages import parse_call_id
    response = (
        "SIP/2.0 180 Ringing\r\n"
        "Via: SIP/2.0/UDP 10.0.0.2:5062;branch=z9hG4bKtest\r\n"
        "Call-ID: sipring-abc12345\r\n"
        "CSeq: 1 INVITE\r\n\r\n"
    )
    assert parse_call_id(response) == "sipring-abc12345"
    assert parse_call_id("SIP/2.0 180 Ringing\r\n\r\n") is None
```

Append to `tests/test_sip_client.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/test_messages.py::test_parse_call_id tests/test_sip_client.py::test_foreign_call_id_responses_are_ignored -v`
Expected: `test_parse_call_id` FAILS with ImportError; the client test FAILS with `assert <CallResult.BUSY> == <CallResult.COMPLETED>`.

- [ ] **Step 3: Implement**

In `sipring/sip/messages.py`, after `parse_to_tag`:

```python
def parse_call_id(response: str) -> Optional[str]:
    """Extract Call-ID from a SIP message."""
    match = re.search(r"^Call-ID:\s*(\S+)", response, re.IGNORECASE | re.MULTILINE)
    return match.group(1) if match else None
```

In `sipring/sip/client.py`: add `parse_call_id` to the `from .messages import (...)` list, then replace the whole `_receive` method with:

```python
    async def _receive(self, timeout: float = 5.0) -> Optional[str]:
        """Receive a SIP response for the current call.

        Responses carrying a different Call-ID (stale retransmissions from a
        previous dialog, or unrelated traffic on the port) are dropped.
        """
        if not self._protocol:
            return None
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return None
            try:
                response = await asyncio.wait_for(
                    self._protocol.response_queue.get(),
                    timeout=remaining,
                )
            except asyncio.TimeoutError:
                return None
            call_id = parse_call_id(response)
            if call_id is not None and self._state.call_id and call_id != self._state.call_id:
                logger.debug(f"Ignoring response for foreign Call-ID {call_id}")
                continue
            code = parse_response_code(response)
            logger.debug(f"Received {code}")
            return response
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sipring/sip/messages.py sipring/sip/client.py tests/test_messages.py tests/test_sip_client.py
git commit -m "Ignore SIP responses that do not match the current Call-ID"
```

---

### Task 3: Retransmit INVITE until the first response

**Files:**
- Modify: `sipring/sip/client.py` (`_send_invite`)
- Test: `tests/test_sip_client.py`

**Interfaces:**
- Consumes: `self.invite_retransmit_interval` (added in Task 1), `_receive` (Task 2 version).
- Produces: `_send_invite` retransmits the INVITE with doubling interval until any response arrives (RFC 3261 Timer A behavior); stops retransmitting after the first response of any kind.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_sip_client.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/test_sip_client.py -v -k retransmi`
Expected: `test_invite_is_retransmitted_until_response` FAILS (`len(...) >= 3` is False; only 1 INVITE sent, result TIMEOUT). The `no_retransmission` test passes trivially today; keep it as a regression guard.

- [ ] **Step 3: Implement**

Replace the deadline loop in `_send_invite` (currently `deadline = ...` through `return False` before the `logger.warning("Timeout...")` line) with:

```python
        loop = asyncio.get_event_loop()
        deadline = loop.time() + 10.0
        retransmit_interval = self.invite_retransmit_interval
        next_retransmit = loop.time() + retransmit_interval
        got_any_response = False

        while loop.time() < deadline:
            if self._cancel_requested:
                return False

            if not got_any_response and loop.time() >= next_retransmit:
                logger.debug("Retransmitting INVITE")
                self._send(message)
                retransmit_interval *= 2
                next_retransmit = loop.time() + retransmit_interval

            wait = min(0.5, deadline - loop.time())
            if not got_any_response:
                wait = min(wait, max(next_retransmit - loop.time(), 0.01))
            response = await self._receive(timeout=wait)
            if response:
                got_any_response = True
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
                    self._state.state = "BUSY"
                    return False
                elif code >= 400:
                    logger.warning(f"Error response: {code}")
                    self._state.state = "TERMINATED"
                    return False
```

(The trailing `logger.warning("Timeout waiting for response")`, `self._state.state = "TIMEOUT"`, `return False` stay unchanged.)

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sipring/sip/client.py tests/test_sip_client.py
git commit -m "Retransmit INVITE with doubling interval until a response arrives"
```

---

### Task 4: ACK non-2xx final responses

**Files:**
- Modify: `sipring/sip/messages.py` (add `build_ack_for_error`, `parse_cseq_method`)
- Modify: `sipring/sip/client.py` (`_ack_error_response` helper, wire into `_send_invite` and `_send_cancel`)
- Test: `tests/test_sip_client.py`, `tests/test_messages.py`

**Interfaces:**
- Consumes: `CallState` (has `branch`, `cseq`, `call_id`, `from_tag`), `parse_to_tag`.
- Produces: `SIPMessage.build_ack_for_error(state: CallState, to_tag: str = "") -> str` (ACK using the INVITE's branch and CSeq number), `parse_cseq_method(response: str) -> Optional[str]` (uppercase method or None), `SIPClient._ack_error_response(response: str) -> None`. Task 5 uses `parse_cseq_method` and `_ack_error_response`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_messages.py`:

```python
def test_build_ack_for_error_uses_invite_branch():
    """Non-2xx ACK must reuse the INVITE branch and CSeq number (RFC 3261)."""
    msg = SIPMessage(
        target_user="1234", target_host="10.0.0.1", target_port=5060,
        caller_name="Test", caller_user="caller",
        local_host="10.0.0.2", local_port=5062,
    )
    state = CallState(call_id="test-1", from_tag="ft1",
                      branch="z9hG4bKinvite1", cseq=1)
    ack = msg.build_ack_for_error(state, to_tag="remote1")
    assert "ACK sip:1234@10.0.0.1 SIP/2.0" in ack
    assert "branch=z9hG4bKinvite1" in ack
    assert "CSeq: 1 ACK" in ack
    assert "To: <sip:1234@10.0.0.1>;tag=remote1" in ack


def test_parse_cseq_method():
    from sipring.sip.messages import parse_cseq_method
    response = "SIP/2.0 200 OK\r\nCSeq: 1 CANCEL\r\n\r\n"
    assert parse_cseq_method(response) == "CANCEL"
    assert parse_cseq_method("SIP/2.0 200 OK\r\n\r\n") is None
```

Append to `tests/test_sip_client.py`:

```python
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
    acks = fake_server.requests("ACK")
    assert len(acks) == 1
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
    assert len(fake_server.requests("ACK")) == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/test_messages.py tests/test_sip_client.py -v -k "ack or cseq_method"`
Expected: FAIL (AttributeError / ImportError / `len(acks) == 1` is 0).

- [ ] **Step 3: Implement**

In `sipring/sip/messages.py`, after `build_ack`:

```python
    def build_ack_for_error(self, state: CallState, to_tag: str = "") -> str:
        """Build ACK for a non-2xx final response.

        RFC 3261 17.1.1.3: this ACK belongs to the INVITE transaction, so it
        reuses the INVITE's branch and CSeq number; the To tag comes from the
        error response.
        """
        to_suffix = f";tag={to_tag}" if to_tag else ""
        return (
            f"ACK sip:{self.target_user}@{self.target_host} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP {self.local_host}:{self.local_port};branch={state.branch}\r\n"
            f"Max-Forwards: 70\r\n"
            f"From: \"{self.caller_name}\" <sip:{self.caller_user}@{self.local_host}>;tag={state.from_tag}\r\n"
            f"To: <sip:{self.target_user}@{self.target_host}>{to_suffix}\r\n"
            f"Call-ID: {state.call_id}\r\n"
            f"CSeq: {state.cseq} ACK\r\n"
            f"Content-Length: 0\r\n"
            f"\r\n"
        )
```

And after `parse_call_id`:

```python
def parse_cseq_method(response: str) -> Optional[str]:
    """Extract the method from a CSeq header (uppercase), or None."""
    match = re.search(r"^CSeq:\s*\d+\s+(\w+)", response, re.IGNORECASE | re.MULTILINE)
    return match.group(1).upper() if match else None
```

In `sipring/sip/client.py`: add `parse_cseq_method` to the messages import list; add this method after `_send`:

```python
    def _ack_error_response(self, response: str) -> None:
        """ACK a non-2xx final response so the peer stops retransmitting it."""
        to_tag = parse_to_tag(response) or ""
        self._send(self._msg_builder.build_ack_for_error(self._state, to_tag))
```

Wire it into `_send_invite` (the Task 3 version): in the `code == 486 or code == 600` branch and the `code >= 400` branch, add `self._ack_error_response(response)` as the first line of each branch.

Wire it into `_send_cancel`: in the `elif code == 487:` branch, add `self._ack_error_response(response)` before `got_487 = True`.

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sipring/sip/messages.py sipring/sip/client.py tests/test_messages.py tests/test_sip_client.py
git commit -m "ACK non-2xx final responses to stop peer retransmissions"
```

---

### Task 5: Handle answer racing a cancel (ACK + BYE, result ANSWERED)

**Files:**
- Modify: `sipring/sip/client.py` (`_send_cancel`, `ring`)
- Test: `tests/test_sip_client.py`

**Interfaces:**
- Consumes: `parse_cseq_method` (Task 4), `_send_bye` (existing; sends ACK then BYE, requires `state.state == "ANSWERED"` and `state.to_tag`).
- Produces: `_send_cancel` returns early with `self._state.state == "ANSWERED"` when a 200-to-INVITE arrives; `ring()` then BYEs and returns `CallResult.ANSWERED`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sip_client.py`:

```python
async def test_answered_during_cancel_sends_ack_and_bye(fake_server):
    """A 200 OK to INVITE arriving after CANCEL must be ACKed and BYEd."""

    def handler(msg):
        if msg.startswith("INVITE "):
            return [sip_response(msg, 180, "Ringing")]
        if msg.startswith("CANCEL "):
            # Phone was picked up just before the CANCEL landed: the INVITE
            # transaction completes with 200 OK instead of 487.
            return [sip_response(msg, 200, "OK", to_tag="gig1", cseq="1 INVITE")]
        if msg.startswith("BYE "):
            return [sip_response(msg, 200, "OK")]
        return []

    fake_server.handler = handler
    client = make_client(fake_server.port)
    result = await client.ring(duration=0.2)

    assert result == CallResult.ANSWERED
    assert len(fake_server.requests("ACK")) == 1
    assert len(fake_server.requests("BYE")) == 1
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/python -m pytest tests/test_sip_client.py::test_answered_during_cancel_sends_ack_and_bye -v`
Expected: FAIL - result is `COMPLETED` (after the 5s cancel deadline) and no BYE was sent. Note: this test takes ~5s before the fix because `_send_cancel` waits out its deadline.

- [ ] **Step 3: Implement**

Replace the response-handling body of the `while` loop in `_send_cancel` with:

```python
            response = await self._receive(timeout=1.0)
            if not response:
                continue
            code = parse_response_code(response)
            method = parse_cseq_method(response)
            if code == 200 and method == "CANCEL":
                logger.debug("Got 200 OK for CANCEL")
                got_200 = True
            elif code == 200 and method == "INVITE":
                # The phone was answered before the CANCEL took effect.
                logger.info("Call answered while cancelling")
                self._state.to_tag = parse_to_tag(response) or ""
                self._state.state = "ANSWERED"
                return False
            elif code == 487:
                self._ack_error_response(response)
                logger.debug("Got 487 Request Terminated")
                got_487 = True
```

(The old string check `"CANCEL" in response` is gone; matching is now on the CSeq method.)

In `ring()`, replace the block after the ring loop:

```python
            notify_state("CANCELING")
            await self._send_cancel()
            if self._state.state == "ANSWERED":
                notify_state("ANSWERED")
                await self._send_bye()
                return CallResult.ANSWERED
            if self._cancel_requested:
                return CallResult.CANCELLED
            return CallResult.COMPLETED
```

And the earlier invite-failure branch becomes:

```python
            if not await self._send_invite():
                if self._cancel_requested:
                    await self._send_cancel()
                    if self._state.state == "ANSWERED":
                        notify_state("ANSWERED")
                        await self._send_bye()
                        return CallResult.ANSWERED
                    return CallResult.CANCELLED
                if self._state.state == "BUSY":
                    return CallResult.BUSY
                if self._state.state == "TIMEOUT":
                    return CallResult.TIMEOUT
                return CallResult.ERROR
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass, and the new test now finishes fast (<1s).

- [ ] **Step 5: Commit**

```bash
git add sipring/sip/client.py tests/test_sip_client.py
git commit -m "Hang up cleanly when the phone is answered during a cancel"
```

---

### Task 6: RFC-compliant INVITE header block

**Files:**
- Modify: `sipring/sip/messages.py` (`build_invite`)
- Test: `tests/test_messages.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `build_invite` output with exactly one `\r\n\r\n`, at the end. All headers (including P-Asserted-Identity, Remote-Party-ID, User-Agent, Content-Length) in one block.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_messages.py`:

```python
def test_build_invite_has_single_header_block():
    """All headers must precede the single blank-line terminator (RFC 3261)."""
    msg = SIPMessage(
        target_user="1234", target_host="10.0.0.1", target_port=5060,
        caller_name="Test", caller_user="caller",
        local_host="10.0.0.2", local_port=5062,
    )
    state = CallState(call_id="test-1", from_tag="ft1",
                      branch="z9hG4bKb1", cseq=1)
    invite = msg.build_invite(state)

    headers, _, body = invite.partition("\r\n\r\n")
    assert body == "", "INVITE must have an empty body"
    assert "P-Asserted-Identity:" in headers
    assert "Remote-Party-ID:" in headers
    assert "User-Agent:" in headers
    assert "Content-Length: 0" in headers
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/python -m pytest tests/test_messages.py::test_build_invite_has_single_header_block -v`
Expected: FAIL - `body` is non-empty (the P-Asserted-Identity block currently sits after the first blank line).

- [ ] **Step 3: Implement**

Replace `build_invite` in `sipring/sip/messages.py` with:

```python
    def build_invite(self, state: CallState) -> str:
        """Build SIP INVITE message."""
        return (
            f"INVITE sip:{self.target_user}@{self.target_host} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP {self.local_host}:{self.local_port};branch={state.branch}\r\n"
            f"Max-Forwards: 70\r\n"
            f"From: \"{self.caller_name}\" <sip:{self.caller_user}@{self.local_host}>;tag={state.from_tag}\r\n"
            f"To: <sip:{self.target_user}@{self.target_host}>\r\n"
            f"Call-ID: {state.call_id}\r\n"
            f"CSeq: {state.cseq} INVITE\r\n"
            f"Contact: <sip:{self.caller_user}@{self.local_host}:{self.local_port}>\r\n"
            f"P-Asserted-Identity: \"{self.caller_name}\" <sip:{self.caller_user}@local>\r\n"
            f"Remote-Party-ID: \"{self.caller_name}\" <sip:{self.caller_user}@local>;party=calling;screen=yes;privacy=off\r\n"
            f"User-Agent: {self.user_agent}\r\n"
            f"Content-Length: 0\r\n"
            f"\r\n"
        )
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sipring/sip/messages.py tests/test_messages.py
git commit -m "Build INVITE as a single RFC-compliant header block"
```

**IMPORTANT for the final task:** this change MUST be verified against the real Gigaset (caller ID display) before release. The old format matched a hardware capture; if caller ID breaks, revert this commit only.

---

### Task 7: Timezone-aware ActiveCall.started_at

**Files:**
- Modify: `sipring/ring_manager.py`
- Test: `tests/test_sip_client.py` (small unit test appended there; no better home exists and it needs no HTTP app)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sip_client.py`:

```python
def test_active_call_started_at_is_timezone_aware():
    from sipring.ring_manager import ActiveCall
    from uuid import uuid4

    call = ActiveCall(config_id=uuid4(), client=None, task=None)
    assert call.started_at.tzinfo is not None
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/python -m pytest tests/test_sip_client.py::test_active_call_started_at_is_timezone_aware -v`
Expected: FAIL - `tzinfo is None` (naive `datetime.utcnow`).

- [ ] **Step 3: Implement**

In `sipring/ring_manager.py`:
- Change the models import line to: `from .models import RingEvent, utc_now`
- Change the dataclass field to: `started_at: datetime = field(default_factory=utc_now)`
- The `from datetime import datetime` import stays (used as a type).

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sipring/ring_manager.py tests/test_sip_client.py
git commit -m "Use timezone-aware timestamps for active call tracking"
```

---

### Task 8: Security module and API auth

**Files:**
- Create: `sipring/security.py`
- Create: `tests/test_auth.py`
- Modify: `sipring/api/config.py`, `sipring/api/events.py`, `sipring/api/ring.py`, `sipring/main.py`

**Interfaces:**
- Produces: `sipring/security.py` with `require_auth(request: Request) -> bool` (FastAPI dependency; no-op when auth disabled, 401 with `WWW-Authenticate: Basic` otherwise) and `get_source_user(request: Request) -> Optional[str]`. Task 9 attaches `require_auth` to its new router.
- Constraint: `/ring/*` and `/health` remain WITHOUT auth (intentional, user decision).

- [ ] **Step 1: Write failing tests**

Create `tests/test_auth.py`:

```python
"""Tests for basic auth on the API and web UI."""

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SIPRING_DATA_DIR", tempfile.mkdtemp())

from sipring.config import get_settings
from sipring.main import app
import sipring.storage as storage_module
from sipring.storage import ConfigStorage


@pytest.fixture(autouse=True)
def reset_storage():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"configs": []}, f)
        temp_path = f.name
    storage_module._storage = ConfigStorage(file_path=temp_path)
    yield
    os.unlink(temp_path)


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("SIPRING_USERNAME", "admin")
    monkeypatch.setenv("SIPRING_PASSWORD", "s3cret")
    get_settings.cache_clear()
    yield TestClient(app)
    get_settings.cache_clear()


def test_api_requires_auth_when_enabled(auth_client):
    assert auth_client.get("/api/configs").status_code == 401
    assert auth_client.get("/api/events").status_code == 401


def test_api_accepts_valid_credentials(auth_client):
    response = auth_client.get("/api/configs", auth=("admin", "s3cret"))
    assert response.status_code == 200


def test_api_rejects_wrong_credentials(auth_client):
    response = auth_client.get("/api/configs", auth=("admin", "wrong"))
    assert response.status_code == 401


def test_ring_endpoints_stay_open(auth_client):
    """/ring is intentionally unauthenticated for IoT trigger devices."""
    response = auth_client.get("/ring/nonexistent-slug")
    assert response.status_code == 404  # not 401


def test_health_stays_open(auth_client):
    assert auth_client.get("/health").status_code == 200


def test_web_ui_requires_auth(auth_client):
    assert auth_client.get("/").status_code == 401


def test_no_auth_configured_means_open(monkeypatch):
    monkeypatch.delenv("SIPRING_USERNAME", raising=False)
    monkeypatch.delenv("SIPRING_PASSWORD", raising=False)
    get_settings.cache_clear()
    client = TestClient(app)
    assert client.get("/api/configs").status_code == 200
    assert client.get("/").status_code == 200
    get_settings.cache_clear()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/test_auth.py -v`
Expected: `test_api_requires_auth_when_enabled` and `test_api_rejects_wrong_credentials` FAIL (API currently open); the web UI test passes (already protected).

- [ ] **Step 3: Implement the security module**

Create `sipring/security.py`:

```python
"""HTTP basic auth helpers.

Auth is enabled by setting SIPRING_USERNAME and SIPRING_PASSWORD. When
enabled it protects the web UI and the /api routes. The /ring endpoints
stay open by design so that simple trigger devices (doorbell buttons,
automations) can call them without credentials.
"""

import base64
import secrets
from typing import Optional

from fastapi import HTTPException, Request, status

from .config import get_settings


def _parse_basic_auth(request: Request) -> Optional[tuple[str, str]]:
    """Return (username, password) from a Basic Authorization header, or None."""
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    try:
        scheme, credentials = auth.split()
        if scheme.lower() != "basic":
            return None
        decoded = base64.b64decode(credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None


def require_auth(request: Request) -> bool:
    """FastAPI dependency: enforce basic auth when it is configured."""
    settings = get_settings()
    if not settings.auth_enabled:
        return True
    parsed = _parse_basic_auth(request)
    if parsed is not None:
        username, password = parsed
        correct_username = secrets.compare_digest(
            username.encode("utf8"), settings.username.encode("utf8")
        )
        correct_password = secrets.compare_digest(
            password.encode("utf8"), settings.password.encode("utf8")
        )
        if correct_username and correct_password:
            return True
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def get_source_user(request: Request) -> Optional[str]:
    """Best-effort extraction of the basic-auth username for event logging."""
    if not get_settings().auth_enabled:
        return None
    parsed = _parse_basic_auth(request)
    return parsed[0] if parsed else None
```

- [ ] **Step 4: Wire it up**

`sipring/api/config.py`:
- Add imports: `from fastapi import APIRouter, Depends, HTTPException, Request` and `from ..security import require_auth, get_source_user`.
- Change the router line to: `router = APIRouter(prefix="/api/configs", tags=["config"], dependencies=[Depends(require_auth)])`
- Delete the local `_get_source_user` function and the now-unused `import base64` and `from ..config import get_settings` if nothing else uses it (`config_to_response` still uses `get_settings`, so keep that import).
- In `test_config`, replace `source_user=_get_source_user(request)` with `source_user=get_source_user(request)`.

`sipring/api/events.py`:
- Add imports: `from fastapi import APIRouter, Depends, Query` and `from ..security import require_auth`.
- Change the router line to: `router = APIRouter(prefix="/api/events", tags=["events"], dependencies=[Depends(require_auth)])`

`sipring/api/ring.py`:
- Add import: `from ..security import get_source_user`.
- Delete the local `_get_source_user` function and the `import base64` line.
- Replace both `source_user=_get_source_user(request)` call sites with `source_user=get_source_user(request)`.
- Do NOT add `require_auth` to this router.

`sipring/main.py`:
- Add import: `from .security import require_auth`.
- Delete the `verify_auth` function, the `optional_auth` function, the `security = HTTPBasic()` line, and the now-unused imports (`secrets`, `HTTPBasic`, `HTTPBasicCredentials`, `status`; keep `Depends` and `HTTPException`).
- Replace every `Depends(optional_auth)` with `Depends(require_auth)` (6 web UI routes).

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. If `tests/test_api.py` fails with 401s, a `get_settings` cache leak between test files is the cause: ensure both fixtures in `tests/test_auth.py` call `get_settings.cache_clear()` on teardown as written.

- [ ] **Step 6: Commit**

```bash
git add sipring/security.py sipring/api/config.py sipring/api/events.py sipring/api/ring.py sipring/main.py tests/test_auth.py
git commit -m "Require basic auth on API routes and centralize auth helpers"
```

---

### Task 9: Active-rings status endpoint

**Files:**
- Modify: `sipring/api/ring.py` (new authenticated router), `sipring/api/__init__.py`, `sipring/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `require_auth` (Task 8), `RingManager.get_active_calls() -> Dict[UUID, str]` (existing).
- Produces: `GET /api/active-rings` returning `{"active": {"<uuid>": "<state>", ...}}`. Exported as `ring_status_router` from `sipring.api`. Task 12's JS polls this endpoint.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api.py`:

```python
def test_active_rings_empty(client):
    response = client.get("/api/active-rings")
    assert response.status_code == 200
    assert response.json() == {"active": {}}


def test_active_rings_reports_states(client):
    from uuid import uuid4
    from sipring.ring_manager import ActiveCall, get_ring_manager

    manager = get_ring_manager()
    config_id = uuid4()
    manager._active_calls[config_id] = ActiveCall(
        config_id=config_id, client=None, task=None, state="RINGING"
    )
    try:
        response = client.get("/api/active-rings")
        assert response.status_code == 200
        assert response.json()["active"] == {str(config_id): "RINGING"}
    finally:
        manager._active_calls.pop(config_id, None)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/test_api.py -v -k active_rings`
Expected: FAIL with 404.

- [ ] **Step 3: Implement**

In `sipring/api/ring.py`, add near the top (after the existing `router = ...` line):

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..security import get_source_user, require_auth

ring_status_router = APIRouter(
    prefix="/api", tags=["ring"], dependencies=[Depends(require_auth)]
)


@ring_status_router.get("/active-rings")
async def active_rings():
    """Current active ring calls, keyed by config id. Polled by the web UI."""
    active = get_ring_manager().get_active_calls()
    return {"active": {str(config_id): state for config_id, state in active.items()}}
```

(Merge the `fastapi` import line with the existing one instead of duplicating it.)

In `sipring/api/__init__.py`, export it alongside the existing routers (mirror the existing style, e.g.):

```python
from .ring import router as ring_router, ring_status_router
```

and add `ring_status_router` to `__all__` if the module defines one.

In `sipring/main.py`, add to the router includes:

```python
app.include_router(ring_status_router)
```

with the corresponding import from `.api`.

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sipring/api/ring.py sipring/api/__init__.py sipring/main.py tests/test_api.py
git commit -m "Add active-rings endpoint for UI status polling"
```

---

### Task 10: JS fetch error handling, safe toasts, dead code removal

**Files:**
- Modify: `sipring/static/js/main.js`

No pytest coverage exists for JS; verification is (a) pages still render via existing pytest, (b) the manual browser check in the final task.

- [ ] **Step 1: Rewrite `showToast` to build DOM nodes (no `innerHTML` for the message)**

Replace the `showToast` function body with:

```javascript
    function showToast(message, type = 'success', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
        use.setAttribute('href', `#icon-${type === 'success' ? 'check' : 'alert'}`);
        svg.appendChild(use);

        const span = document.createElement('span');
        span.className = 'toast-message';
        span.textContent = message;

        toast.append(svg, span);
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('toast-out');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
```

- [ ] **Step 2: Rewrite `triggerRing` and `testRing` with `response.ok` handling**

Replace both functions with:

```javascript
    async function triggerRing(url, button) {
        const originalHtml = button.innerHTML;
        button.innerHTML = '<svg class="spin"><use href="#icon-bell"></use></svg> Ringing...';
        button.disabled = true;

        try {
            const response = await fetch(url);
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.detail || `Request failed (${response.status})`);
            }
            button.innerHTML = `<svg><use href="#icon-check"></use></svg> ${data.status || 'Done'}`;
            showToast(data.message || data.status || 'Ring triggered');
        } catch (error) {
            button.innerHTML = '<svg><use href="#icon-alert"></use></svg> Error';
            showToast(error.message || 'Failed to trigger ring', 'error');
        } finally {
            setTimeout(() => {
                button.innerHTML = originalHtml;
                button.disabled = false;
            }, 3000);
        }
    }

    window.triggerRing = triggerRing;

    async function testRing(configId, button) {
        const originalHtml = button.innerHTML;
        button.innerHTML = '<svg class="spin"><use href="#icon-test"></use></svg> Testing...';
        button.disabled = true;

        try {
            const response = await fetch(`/api/configs/${configId}/test`, { method: 'POST' });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.detail || `Request failed (${response.status})`);
            }
            button.innerHTML = `<svg><use href="#icon-check"></use></svg> ${data.result || 'Done'}`;
            showToast(data.result ? `Test result: ${data.result}` : 'Test completed');
        } catch (error) {
            button.innerHTML = '<svg><use href="#icon-alert"></use></svg> Error';
            showToast(error.message || 'Test failed', 'error');
        } finally {
            setTimeout(() => {
                button.innerHTML = originalHtml;
                button.disabled = false;
            }, 3000);
        }
    }

    window.testRing = testRing;
```

(The section-comment banners around them stay as they are.)

- [ ] **Step 3: Remove the duplicated empty "Active Nav Item" section**

Delete the first, empty `// Active Nav Item` comment banner (the one directly above the "Local Timezone Conversion" section, `main.js` around lines 356-359). Keep the real one at the bottom.

- [ ] **Step 4: Verify pages still render and commit**

Run: `.venv/bin/python -m pytest -q` (sanity: no server-side change, must stay green)
Optionally: `node --check sipring/static/js/main.js` if node is installed, for a syntax check.

```bash
git add sipring/static/js/main.js
git commit -m "Handle API errors in ring actions and build toasts safely"
```

---

### Task 11: Data-attribute event delegation (quote-safe handlers)

**Files:**
- Modify: `sipring/templates/dashboard.html`, `sipring/templates/config_detail.html`, `sipring/static/js/main.js`

**Interfaces:**
- Produces: buttons carry `data-action` (`ring` | `cancel` | `test` | `clone` | `delete` | `copy`) plus `data-url`, `data-config-id`, `data-config-name`, or `data-copy-text` as needed. One delegated click listener dispatches them. Task 12 adds `data-action="cancel"` buttons that reuse this dispatcher.

- [ ] **Step 1: Convert dashboard.html buttons**

In `sipring/templates/dashboard.html` replace the inline handlers:

- Ring button: `<button class="btn btn-primary btn-sm" data-action="ring" data-url="{{ item.ring_url }}">`
- Test button: `<button class="btn btn-secondary btn-sm" data-action="test" data-config-id="{{ item.config.id }}">`
- Copy button: `<button class="btn-copy" data-action="copy" data-copy-text="{{ item.ring_url }}" title="Copy URL">`
- Clone button: `<button class="btn btn-ghost btn-sm" data-action="clone" data-config-id="{{ item.config.id }}">`
- Delete button: `<button class="btn btn-ghost btn-sm text-error" data-action="delete" data-config-id="{{ item.config.id }}" data-config-name="{{ item.config.name }}">`

(SVG/text children stay unchanged; only the attributes change. Jinja autoescaping makes quotes in `name` safe inside a double-quoted attribute.)

- [ ] **Step 2: Convert config_detail.html buttons**

Same pattern in `sipring/templates/config_detail.html`:

- "Ring Now": `data-action="ring" data-url="{{ ring_url }}"`
- Cancel (inside the `{% if is_ringing %}`): `data-action="cancel" data-url="{{ cancel_url }}"` (Task 12 restructures this button; the attribute shape stays)
- Both copy buttons: `data-action="copy" data-copy-text="{{ ring_url }}"` / `data-copy-text="{{ cancel_url }}"`
- "Test (3s)": `data-action="test" data-config-id="{{ config.id }}"`
- Clone: `data-action="clone" data-config-id="{{ config.id }}"`
- Delete: `data-action="delete" data-config-id="{{ config.id }}" data-config-name="{{ config.name }}"`

- [ ] **Step 3: Add the delegated listener to main.js**

Add a new section before the "Form Handling" section:

```javascript
    // ==========================================================================
    // Action Button Delegation
    // ==========================================================================

    document.addEventListener('click', (e) => {
        const el = e.target.closest('[data-action]');
        if (!el) return;
        const d = el.dataset;
        switch (d.action) {
            case 'ring':
            case 'cancel':
                triggerRing(d.url, el);
                break;
            case 'test':
                testRing(d.configId, el);
                break;
            case 'clone':
                cloneConfig(d.configId);
                break;
            case 'delete':
                deleteConfig(d.configId, d.configName);
                break;
            case 'copy':
                copyToClipboard(d.copyText, el);
                break;
        }
    });
```

Leave `window.triggerRing` etc. exposed - `events.html` still uses inline `onclick` for numeric-only pagination (`loadPage(50)`) and the filter form, which cannot contain user text and are out of scope.

- [ ] **Step 4: Verify and commit**

Run: `.venv/bin/python -m pytest -q`
Grep check: `grep -n "onclick" sipring/templates/dashboard.html sipring/templates/config_detail.html` must return nothing.

```bash
git add sipring/templates/dashboard.html sipring/templates/config_detail.html sipring/static/js/main.js
git commit -m "Replace inline onclick handlers with data-attribute delegation"
```

---

### Task 12: Live ring status polling and dynamic Cancel buttons

**Files:**
- Modify: `sipring/templates/dashboard.html`, `sipring/templates/config_detail.html`, `sipring/static/js/main.js`

**Interfaces:**
- Consumes: `GET /api/active-rings` (Task 9), `data-action="cancel"` dispatch (Task 11).
- Produces: cards marked `data-config-card data-config-id="<uuid>"` with child elements `[data-ring-badge]`, `[data-idle-badge]`, `[data-action="cancel"]`; a `[data-active-count]` counter on the dashboard. Poll interval 2500ms, paused while the tab is hidden.

- [ ] **Step 1: Restructure dashboard.html for dynamic state**

In `sipring/templates/dashboard.html`:

1. Card root: `<div class="card" data-config-card data-config-id="{{ item.config.id }}">`
2. Active count stat: `<div class="stat-value has-pulse"><span data-active-count>{{ active_count }}</span> ...`
3. Replace the badge `{% if %}` chain in `card-header-left` so both badges always exist and visibility is attribute-driven:

```html
                <span class="badge badge-info" data-ring-badge {% if not item.is_ringing %}hidden{% endif %}>
                    <span class="status-dot status-dot-info pulse"></span>
                    Ringing
                </span>
                <span data-idle-badge {% if item.is_ringing %}hidden{% endif %}>
                    {% if item.config.enabled %}
                    <span class="badge badge-success">
                        <span class="status-dot status-dot-success"></span>
                        Enabled
                    </span>
                    {% else %}
                    <span class="badge badge-warning">
                        <span class="status-dot status-dot-warning"></span>
                        Disabled
                    </span>
                    {% endif %}
                </span>
```

4. Add a Cancel button to `card-actions`, after the Ring button:

```html
                <button class="btn btn-secondary btn-sm" data-action="cancel"
                        data-url="{{ item.cancel_url }}"
                        {% if not item.is_ringing %}hidden{% endif %}>
                    <svg><use href="#icon-stop"></use></svg>
                    Cancel
                </button>
```

- [ ] **Step 2: Restructure config_detail.html the same way**

1. Wrap: add `data-config-card data-config-id="{{ config.id }}"` to the `page-header` div (it contains both the badges and the action buttons).
2. Badges: same `data-ring-badge` / `data-idle-badge` + `hidden` pattern as the dashboard, driven by `is_ringing` (the ringing badge keeps its `Ringing ({{ ring_state }})` text; the polled update may simply show "Ringing").
3. Cancel button: remove the surrounding `{% if is_ringing %}...{% endif %}` and instead render it always with `{% if not is_ringing %}hidden{% endif %}`, keeping `data-action="cancel" data-url="{{ cancel_url }}"` from Task 11.

- [ ] **Step 3: Add the poller to main.js**

New section after "Action Button Delegation":

```javascript
    // ==========================================================================
    // Live Ring Status Polling
    // ==========================================================================

    const POLL_INTERVAL_MS = 2500;

    function updateRingIndicators(active) {
        document.querySelectorAll('[data-config-card]').forEach(card => {
            const ringing = Object.prototype.hasOwnProperty.call(active, card.dataset.configId);
            const ringBadge = card.querySelector('[data-ring-badge]');
            const idleBadge = card.querySelector('[data-idle-badge]');
            const cancelBtn = card.querySelector('[data-action="cancel"]');
            if (ringBadge) ringBadge.hidden = !ringing;
            if (idleBadge) idleBadge.hidden = ringing;
            if (cancelBtn) cancelBtn.hidden = !ringing;
        });
        const counter = document.querySelector('[data-active-count]');
        if (counter) counter.textContent = Object.keys(active).length;
    }

    async function refreshActiveRings() {
        try {
            const response = await fetch('/api/active-rings');
            if (!response.ok) return;
            const data = await response.json();
            updateRingIndicators(data.active || {});
        } catch (error) {
            // Server unreachable; leave the UI as-is and retry on the next tick.
        }
    }

    if (document.querySelector('[data-config-card]')) {
        setInterval(() => {
            if (!document.hidden) refreshActiveRings();
        }, POLL_INTERVAL_MS);
    }
```

Also add a `refreshActiveRings()` call inside `triggerRing`'s success path (right after `showToast(...)`), so the Cancel button appears immediately after triggering. Guard it: `if (typeof refreshActiveRings === 'function') refreshActiveRings();` is unnecessary within the same IIFE; a plain call is fine since the poller section is defined before first use at runtime (function declarations hoist within the IIFE).

- [ ] **Step 4: Verify and commit**

Run: `.venv/bin/python -m pytest -q` (template changes must not break rendering; `test_api.py`/`test_auth.py` cover `/` rendering when auth is off... note: existing suite has no explicit dashboard-render test with configs; add one now):

Append to `tests/test_api.py`:

```python
def test_dashboard_renders_config_cards(client):
    client.post("/api/configs", json={
        "name": "Poll Test", "sip_user": "**610",
        "sip_server": "192.168.1.100", "caller_name": "Bell",
    })
    response = client.get("/")
    assert response.status_code == 200
    assert 'data-config-card' in response.text
    assert 'data-ring-badge' in response.text
```

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

```bash
git add sipring/templates/dashboard.html sipring/templates/config_detail.html sipring/static/js/main.js tests/test_api.py
git commit -m "Poll active rings to update badges and show Cancel while ringing"
```

---

### Task 13: Self-host the Inter font

**Files:**
- Create: `sipring/static/fonts/inter-400.woff2`, `inter-500.woff2`, `inter-600.woff2`, `inter-700.woff2`
- Modify: `sipring/static/css/main.css`, `sipring/templates/base.html`

- [ ] **Step 1: Download the four latin woff2 files**

Run this script (network access required):

```bash
python3 - <<'EOF'
import re, urllib.request, pathlib

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
url = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
req = urllib.request.Request(url, headers={"User-Agent": UA})
css = urllib.request.urlopen(req).read().decode()

out = pathlib.Path("sipring/static/fonts")
out.mkdir(parents=True, exist_ok=True)

# Each latin block: /* latin */ @font-face { ... font-weight: NNN ... url(...woff2) ... }
blocks = re.findall(r"/\* latin \*/\s*@font-face\s*{(.*?)}", css, re.DOTALL)
for block in blocks:
    weight = re.search(r"font-weight:\s*(\d+)", block).group(1)
    src = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
    dest = out / f"inter-{weight}.woff2"
    urllib.request.urlretrieve(src, dest)
    print(f"{dest} <- {src} ({dest.stat().st_size} bytes)")
EOF
```

Verify: four files exist, each larger than 10 KB (`ls -la sipring/static/fonts/`).

- [ ] **Step 2: Add @font-face rules to main.css**

At the very top of `sipring/static/css/main.css` (before the `:root` block), insert:

```css
/* Self-hosted Inter (latin subset), replacing the Google Fonts CDN */
@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 400;
    font-display: swap;
    src: url('/static/fonts/inter-400.woff2') format('woff2');
}
@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 500;
    font-display: swap;
    src: url('/static/fonts/inter-500.woff2') format('woff2');
}
@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 600;
    font-display: swap;
    src: url('/static/fonts/inter-600.woff2') format('woff2');
}
@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 700;
    font-display: swap;
    src: url('/static/fonts/inter-700.woff2') format('woff2');
}
```

- [ ] **Step 3: Remove the Google Fonts links from base.html**

Delete these three lines from `sipring/templates/base.html`:

```html
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

- [ ] **Step 4: Verify and commit**

Run: `grep -rn "fonts.googleapis\|fonts.gstatic" sipring/` - must return nothing.
Run: `.venv/bin/python -m pytest -q` - all pass.

```bash
git add sipring/static/fonts sipring/static/css/main.css sipring/templates/base.html
git commit -m "Self-host the Inter font instead of loading it from Google Fonts"
```

---

### Task 14: Documentation updates

**Files:**
- Modify: `CLAUDE.md`, `README.md`

Reminder (user-facing text): plain hyphens only, no em-dashes.

- [ ] **Step 1: Update CLAUDE.md**

1. In "Key Decisions > SIP Protocol", replace item 5's sentence "Format based on working capture from `invite_haustuer_clean.sip`." with: "The INVITE is a single RFC-compliant header block (see `sipring/sip/messages.py`); the original hardware capture file `invite_haustuer_clean.sip` no longer exists in the repo."
2. Add to "Key Decisions > SIP Protocol" a new item:

```markdown
6. **Client-side robustness** (implemented 2026-09-01):
   - INVITE is retransmitted with a doubling interval until the first response (RFC 3261 Timer A style)
   - Non-2xx final responses (486, 487, 4xx) are ACKed so the peer stops retransmitting them
   - Received responses are filtered by Call-ID; stale packets from earlier dialogs are dropped
   - A 200 OK to INVITE arriving during CANCEL is handled with ACK + BYE (result: answered)
```

3. Add to "Key Decisions > Architecture":

```markdown
5. **Auth model**: When `SIPRING_USERNAME`/`SIPRING_PASSWORD` are set, the web UI and `/api/*` require basic auth (see `sipring/security.py`). The `/ring/*` and `/health` endpoints are intentionally unauthenticated so simple trigger devices can call them.
```

4. In "Reference Files", remove the `invite_haustuer_clean.sip` bullet (the file is gone) and replace with: "`sipring/sip/messages.py` - canonical SIP message formats (INVITE/CANCEL/ACK/BYE)".
5. In "Learnings", update item 1 to: "**SIP Message Format**: The INVITE was originally built with blank lines mid-headers to mirror a hardware capture; since 2026-09-01 it is a single RFC-compliant header block, verified against the Gigaset N670."  (Only write "verified" after the manual hardware test in Task 15 actually passes; if executing before that, write "pending hardware verification" and fix it in Task 15.)
6. In the "API Endpoints" table, add the row: `| GET | /api/active-rings | Active ring states (for UI polling) |`

- [ ] **Step 2: Update README.md**

1. Near the `SIPRING_USERNAME`/`SIPRING_PASSWORD` rows (around line 125), add after the table: "When basic auth is configured, the web UI and the /api endpoints require it. The /ring endpoints stay open by design so trigger devices (doorbell buttons, home automation) work without credentials."
2. Replace line ~165 "Authentication is not currently implemented but can be added if needed." with: "SIP authentication is not currently implemented but can be added if needed (HTTP basic auth for the web UI and API is available via SIPRING_USERNAME/SIPRING_PASSWORD)."

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "Document auth model, SIP robustness changes, and active-rings endpoint"
```

---

### Task 15: Final verification and hardware test checklist

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass, runtime under ~15s.

- [ ] **Step 2: Import and app-boot smoke test**

Run: `.venv/bin/python -c "from sipring.main import app; print(app.version, len(app.routes), 'routes')"`
Expected: prints `0.3.9` and a route count without errors.

- [ ] **Step 3: JS syntax check (if node available)**

Run: `node --check sipring/static/js/main.js`
Expected: no output (valid syntax). Skip if node is not installed.

- [ ] **Step 4: Report to Jordi with the manual verification checklist**

The following can only be verified on the real network and MUST pass before release (the RFC INVITE change in Task 6 carries caller-ID-display risk):

1. Start SIPring locally and trigger a real ring against the Gigaset N670: phone rings, display shows the configured caller name (e.g. "Klingel (Haustür)").
2. Let the ring time out: ringing stops promptly (CANCEL + 487 ACKed, no lingering retransmissions in a `tcpdump -n udp port 5060` capture).
3. Trigger and cancel via the dashboard Cancel button: button appears while ringing, ringing stops.
4. Answer a test ring on the phone: call terminates immediately (ACK + BYE), event log shows "answered".
5. Browser check of the UI: live badge updates while ringing, error toast on ringing a disabled config, dark/light theme, fonts load with Google Fonts unreachable (dev tools offline for fonts.googleapis.com).

If caller ID display breaks in check 1: revert the Task 6 commit only (`git revert <sha>`), update the Task 6 CLAUDE.md learning accordingly, and re-run the suite.

- [ ] **Step 5: Hold for release**

Do NOT push or release. When Jordi gives the go: re-read `crystalline://jordi/reference/release-and-release-notes-convention` and follow it (push branch, wait for CI, tag v0.3.9, then curate release notes with New & Noteworthy / Fixes / Breaking changes sections via `gh release edit`).

---

## Self-Review Notes

- Spec coverage: 2.1→Task 3, 2.2→Task 4, 2.3→Task 2, 2.4→Task 5, 2.6→Tasks 7+8+14, 2.7→Tasks 6+15, 3.1/3.2→Tasks 9+12, 3.3→Task 10, 3.4→Task 11, 3.5→Task 13, 3.6→Task 10. Dependency bump was done pre-plan (commit 284f3f5).
- Type consistency: `invite_retransmit_interval` introduced in Task 1 and consumed in Task 3; `parse_cseq_method`/`_ack_error_response` introduced in Task 4, consumed in Task 5; `require_auth` introduced in Task 8, consumed in Task 9; `data-action="cancel"` dispatch introduced in Task 11, consumed in Task 12.
- Ordering constraint: Tasks 1-6 must run in order (each edits `client.py` on top of the previous). Tasks 10-12 must run in order (each edits `main.js`). Tasks 7, 13 are independent. Task 8 precedes 9; 9 precedes 12; 14 and 15 come last.
