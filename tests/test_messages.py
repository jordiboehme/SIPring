"""Tests for SIP message construction."""

import pytest

from sipring.sip.messages import (
    SIPMessage,
    CallState,
    generate_call_id,
    generate_branch,
    generate_tag,
    parse_response_code,
    parse_to_tag,
)


def test_generate_call_id():
    """Test Call-ID generation."""
    call_id = generate_call_id("test")
    assert call_id.startswith("test-")
    assert len(call_id) == 13  # "test-" + 8 chars


def test_generate_branch():
    """Test branch generation starts with magic cookie."""
    branch = generate_branch()
    assert branch.startswith("z9hG4bK")


def test_generate_tag():
    """Test tag generation."""
    tag = generate_tag()
    assert len(tag) == 8


def test_build_invite():
    """Test INVITE message construction."""
    msg = SIPMessage(
        target_user="1234",
        target_host="10.0.0.1",
        target_port=5060,
        caller_name="Test Caller",
        caller_user="caller",
        local_host="10.0.0.2",
        local_port=5062,
    )

    state = CallState(
        call_id="test-12345678",
        from_tag="abcd1234",
        branch="z9hG4bKtest1234",
        cseq=1,
    )

    invite = msg.build_invite(state)

    assert "INVITE sip:1234@10.0.0.1 SIP/2.0" in invite
    assert "Via: SIP/2.0/UDP 10.0.0.2:5062;branch=z9hG4bKtest1234" in invite
    assert 'From: "Test Caller" <sip:caller@10.0.0.2>;tag=abcd1234' in invite
    assert "To: <sip:1234@10.0.0.1>" in invite
    assert "Call-ID: test-12345678" in invite
    assert "CSeq: 1 INVITE" in invite


def test_build_cancel_matches_invite():
    """Test CANCEL message matches INVITE headers."""
    msg = SIPMessage(
        target_user="1234",
        target_host="10.0.0.1",
        target_port=5060,
        caller_name="Test",
        caller_user="caller",
        local_host="10.0.0.2",
        local_port=5062,
    )

    state = CallState(
        call_id="test-12345678",
        from_tag="abcd1234",
        branch="z9hG4bKtest1234",
        cseq=1,
    )

    cancel = msg.build_cancel(state)

    # CANCEL must have same Request-URI, Call-ID, From, Via, CSeq number
    assert "CANCEL sip:1234@10.0.0.1 SIP/2.0" in cancel
    assert "Call-ID: test-12345678" in cancel
    assert "branch=z9hG4bKtest1234" in cancel
    assert "tag=abcd1234" in cancel
    assert "CSeq: 1 CANCEL" in cancel  # Same number, different method


def test_build_bye_requires_to_tag():
    """Test BYE message includes To-tag."""
    msg = SIPMessage(
        target_user="1234",
        target_host="10.0.0.1",
        target_port=5060,
        caller_name="Test",
        caller_user="caller",
        local_host="10.0.0.2",
        local_port=5062,
    )

    state = CallState(
        call_id="test-12345678",
        from_tag="abcd1234",
        to_tag="efgh5678",  # Required for BYE
        branch="z9hG4bKtest1234",
        cseq=1,
    )

    bye = msg.build_bye(state)

    assert "BYE sip:1234@10.0.0.1 SIP/2.0" in bye
    assert "tag=efgh5678" in bye  # To-tag
    assert "CSeq: 2 BYE" in bye  # Incremented CSeq


def test_parse_response_code():
    """Test SIP response code parsing."""
    assert parse_response_code("SIP/2.0 100 Trying") == 100
    assert parse_response_code("SIP/2.0 180 Ringing") == 180
    assert parse_response_code("SIP/2.0 200 OK") == 200
    assert parse_response_code("SIP/2.0 487 Request Terminated") == 487
    assert parse_response_code("Invalid") == 0


def test_parse_to_tag():
    """Test To-tag parsing from response."""
    response = """SIP/2.0 200 OK
Via: SIP/2.0/UDP 10.0.0.2:5062;branch=z9hG4bKtest
From: "Test" <sip:caller@10.0.0.2>;tag=from123
To: <sip:1234@10.0.0.1>;tag=to456
Call-ID: test-123"""

    tag = parse_to_tag(response)
    assert tag == "to456"


def test_parse_to_tag_not_present():
    """Test To-tag parsing when not present."""
    response = """SIP/2.0 180 Ringing
To: <sip:1234@10.0.0.1>"""

    tag = parse_to_tag(response)
    assert tag is None


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
    assert "User-Agent:" in headers
    assert "Content-Length: 0" in headers


def test_build_invite_has_no_identity_headers():
    """P-Asserted-Identity/Remote-Party-ID must be absent: the Gigaset prefers
    them over From for CLIP and fails to extract a number from their dummy URI,
    which breaks phonebook matching (observed on the N670, 2026-09-01)."""
    msg = SIPMessage(
        target_user="1234", target_host="10.0.0.1", target_port=5060,
        caller_name="Test", caller_user="#107#1",
        local_host="10.0.0.2", local_port=5062,
    )
    state = CallState(call_id="test-1", from_tag="ft1",
                      branch="z9hG4bKb1", cseq=1)
    invite = msg.build_invite(state)

    assert "P-Asserted-Identity" not in invite
    assert "Remote-Party-ID" not in invite
    # CLIP comes from the From user part, so it must carry caller_user verbatim
    assert 'From: "Test" <sip:#107#1@10.0.0.2>;tag=ft1' in invite
