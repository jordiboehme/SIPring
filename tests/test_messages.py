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
