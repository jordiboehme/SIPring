"""SIP Digest Authentication (RFC 2617).

Note: Not currently used as the Gigaset N670 accepts INVITE from LAN
without authentication. Implemented for future use if needed.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DigestChallenge:
    """Parsed WWW-Authenticate challenge."""
    realm: str
    nonce: str
    algorithm: str = "MD5"
    qop: Optional[str] = None
    opaque: Optional[str] = None


def parse_www_authenticate(header: str) -> Optional[DigestChallenge]:
    """Parse WWW-Authenticate header value."""
    if not header.startswith("Digest "):
        return None

    params = {}
    pattern = r'(\w+)=["\']?([^"\']+)["\']?'
    for match in re.finditer(pattern, header):
        params[match.group(1).lower()] = match.group(2)

    if "realm" not in params or "nonce" not in params:
        return None

    return DigestChallenge(
        realm=params["realm"],
        nonce=params["nonce"],
        algorithm=params.get("algorithm", "MD5"),
        qop=params.get("qop"),
        opaque=params.get("opaque"),
    )


def compute_digest_response(
    username: str,
    password: str,
    realm: str,
    nonce: str,
    method: str,
    uri: str,
    algorithm: str = "MD5",
) -> str:
    """Compute digest authentication response hash."""
    def md5_hash(data: str) -> str:
        return hashlib.md5(data.encode('utf-8')).hexdigest()

    # HA1 = MD5(username:realm:password)
    ha1 = md5_hash(f"{username}:{realm}:{password}")

    # HA2 = MD5(method:uri)
    ha2 = md5_hash(f"{method}:{uri}")

    # Response = MD5(HA1:nonce:HA2)
    response = md5_hash(f"{ha1}:{nonce}:{ha2}")

    return response


def build_authorization_header(
    username: str,
    password: str,
    challenge: DigestChallenge,
    method: str,
    uri: str,
) -> str:
    """Build Authorization header value for digest auth."""
    response = compute_digest_response(
        username=username,
        password=password,
        realm=challenge.realm,
        nonce=challenge.nonce,
        method=method,
        uri=uri,
        algorithm=challenge.algorithm,
    )

    parts = [
        f'Digest username="{username}"',
        f'realm="{challenge.realm}"',
        f'nonce="{challenge.nonce}"',
        f'uri="{uri}"',
        f'response="{response}"',
        f'algorithm={challenge.algorithm}',
    ]

    if challenge.opaque:
        parts.append(f'opaque="{challenge.opaque}"')

    return ", ".join(parts)
