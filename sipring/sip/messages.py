"""SIP message construction."""

import random
import re
import string
from dataclasses import dataclass
from typing import Optional


def generate_call_id(prefix: str = "sipring") -> str:
    """Generate unique Call-ID."""
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}-{rand}"


def generate_branch() -> str:
    """Generate unique branch parameter (must start with z9hG4bK per RFC 3261)."""
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"z9hG4bK{rand}"


def generate_tag() -> str:
    """Generate unique tag for From/To headers."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))


@dataclass
class CallState:
    """Tracks state of a SIP call."""
    call_id: str = ""
    from_tag: str = ""
    to_tag: str = ""
    cseq: int = 1
    branch: str = ""
    state: str = "IDLE"  # IDLE, INVITING, RINGING, ANSWERED, CANCELING, TERMINATED


class SIPMessage:
    """SIP message builder."""

    def __init__(
        self,
        target_user: str,
        target_host: str,
        target_port: int,
        caller_name: str,
        caller_user: str,
        local_host: str,
        local_port: int,
        user_agent: str = "SIPring",
    ):
        self.target_user = target_user
        self.target_host = target_host
        self.target_port = target_port
        self.caller_name = caller_name
        self.caller_user = caller_user
        self.local_host = local_host
        self.local_port = local_port
        self.user_agent = user_agent

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
            f"\r\n"
            f"P-Asserted-Identity: \"{self.caller_name}\" <sip:{self.caller_user}@local>\r\n"
            f"Remote-Party-ID: \"{self.caller_name}\" <sip:{self.caller_user}@local>;party=calling;screen=yes;privacy=off\r\n"
            f"\r\n"
            f"User-Agent: {self.user_agent}\r\n"
            f"Content-Length: 0\r\n"
            f"\r\n"
        )

    def build_cancel(self, state: CallState) -> str:
        """Build SIP CANCEL message."""
        return (
            f"CANCEL sip:{self.target_user}@{self.target_host} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP {self.local_host}:{self.local_port};branch={state.branch}\r\n"
            f"Max-Forwards: 70\r\n"
            f"From: \"{self.caller_name}\" <sip:{self.caller_user}@{self.local_host}>;tag={state.from_tag}\r\n"
            f"To: <sip:{self.target_user}@{self.target_host}>\r\n"
            f"Call-ID: {state.call_id}\r\n"
            f"CSeq: {state.cseq} CANCEL\r\n"
            f"Content-Length: 0\r\n"
            f"\r\n"
        )

    def build_bye(self, state: CallState) -> str:
        """Build SIP BYE message."""
        new_branch = generate_branch()
        new_cseq = state.cseq + 1
        return (
            f"BYE sip:{self.target_user}@{self.target_host} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP {self.local_host}:{self.local_port};branch={new_branch}\r\n"
            f"Max-Forwards: 70\r\n"
            f"From: \"{self.caller_name}\" <sip:{self.caller_user}@{self.local_host}>;tag={state.from_tag}\r\n"
            f"To: <sip:{self.target_user}@{self.target_host}>;tag={state.to_tag}\r\n"
            f"Call-ID: {state.call_id}\r\n"
            f"CSeq: {new_cseq} BYE\r\n"
            f"Content-Length: 0\r\n"
            f"\r\n"
        )

    def build_ack(self, state: CallState) -> str:
        """Build SIP ACK message."""
        new_branch = generate_branch()
        return (
            f"ACK sip:{self.target_user}@{self.target_host} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP {self.local_host}:{self.local_port};branch={new_branch}\r\n"
            f"Max-Forwards: 70\r\n"
            f"From: \"{self.caller_name}\" <sip:{self.caller_user}@{self.local_host}>;tag={state.from_tag}\r\n"
            f"To: <sip:{self.target_user}@{self.target_host}>;tag={state.to_tag}\r\n"
            f"Call-ID: {state.call_id}\r\n"
            f"CSeq: {state.cseq} ACK\r\n"
            f"Content-Length: 0\r\n"
            f"\r\n"
        )


def parse_response_code(response: str) -> int:
    """Extract response code from SIP response."""
    match = re.match(r"SIP/2\.0 (\d+)", response)
    return int(match.group(1)) if match else 0


def parse_to_tag(response: str) -> Optional[str]:
    """Extract To-tag from SIP response."""
    match = re.search(r"To:.*?;tag=([^\s;>]+)", response, re.IGNORECASE)
    return match.group(1) if match else None
