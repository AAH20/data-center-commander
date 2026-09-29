"""JWT token creation, decoding, and verification.

Uses HS256 (HMAC-SHA256) with a shared secret — suitable for a single-service
deployment. For multi-service or asymmetric-key scenarios, swap the signing
logic for RS256/ES256 without changing the public API.

All functions are pure and side-effect-free; secrets are never logged.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "JWTClaims",
    "JWTError",
    "create_jwt",
    "decode_jwt",
    "verify_jwt",
]


class JWTError(Exception):
    """Base exception for JWT operations."""


class JWTExpiredError(JWTError):
    """Raised when a token has expired."""


class JWTInvalidError(JWTError):
    """Raised when a token is malformed or has a bad signature."""


class JWTAlgorithmError(JWTError):
    """Raised when the algorithm is unsupported."""


# ---------------------------------------------------------------------------
# Base64url helpers (stdlib only, no padding)
# ---------------------------------------------------------------------------


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("ascii"))


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class JWTClaims:
    """Parsed JWT claims with typed accessors.

    Registered claims (RFC 7519):
    - ``sub`` — subject (user or service ID)
    - ``iss`` — issuer
    - ``aud`` — audience
    - ``exp`` — expiration time (Unix timestamp)
    - ``nbf`` — not-before time (Unix timestamp)
    - ``iat`` — issued-at time (Unix timestamp)
    - ``jti`` — unique token ID

    Custom claims are available via :attr:`raw`.
    """

    sub: str | None = None
    iss: str | None = None
    aud: str | None = None
    exp: int | None = None
    nbf: int | None = None
    iat: int | None = None
    jti: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.exp is None:
            return False
        return time.time() >= self.exp

    @property
    def is_active(self) -> bool:
        now = time.time()
        if self.exp is not None and now >= self.exp:
            return False
        if self.nbf is not None and now < self.nbf:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert claims to a JSON-serializable dict (only non-None fields)."""
        result: dict[str, Any] = {}
        for key in ("sub", "iss", "aud", "exp", "nbf", "iat", "jti"):
            val = getattr(self, key)
            if val is not None:
                result[key] = val
        # Merge custom claims
        for key, val in self.raw.items():
            if key not in result:
                result[key] = val
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JWTClaims:
        """Build a JWTClaims from a dict, separating registered from custom."""
        registered = {"sub", "iss", "aud", "exp", "nbf", "iat", "jti"}
        kwargs: dict[str, Any] = {}
        custom: dict[str, Any] = {}
        for key, val in data.items():
            if key in registered:
                kwargs[key] = val
            else:
                custom[key] = val
        kwargs["raw"] = custom
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# JWT creation
# ---------------------------------------------------------------------------


def create_jwt(
    claims: JWTClaims | dict[str, Any],
    *,
    secret: str | bytes,
    algorithm: str = "HS256",
    headers: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT token.

    Parameters
    ----------
    claims:
        A JWTClaims instance or a dict of claims to encode.
    secret:
        The HMAC secret (string or bytes).
    algorithm:
        Only ``HS256`` is supported.
    headers:
        Additional JWT header fields (e.g. ``{"kid": "key-1"}``).

    Returns
    -------
    str
        The compact JWS string: ``header.payload.signature``.

    Raises
    ------
    JWTAlgorithmError
        If the algorithm is not ``HS256``.
    """
    if algorithm != "HS256":
        raise JWTAlgorithmError(f"unsupported algorithm: {algorithm}")

    if isinstance(claims, JWTClaims):
        payload = claims.to_dict()
    else:
        payload = dict(claims)

    # Auto-add iat and jti if missing
    now = int(time.time())
    if "iat" not in payload:
        payload["iat"] = now
    if "jti" not in payload:
        payload["jti"] = secrets.token_hex(16)

    header: dict[str, Any] = {"alg": algorithm, "typ": "JWT"}
    if headers:
        header.update(headers)

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())

    signing_input = f"{header_b64}.{payload_b64}".encode()
    sig = _sign(signing_input, secret)
    sig_b64 = _b64url_encode(sig)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


# ---------------------------------------------------------------------------
# JWT decoding (no verification)
# ---------------------------------------------------------------------------


def decode_jwt(token: str) -> tuple[dict[str, Any], JWTClaims]:
    """Decode a JWT without verifying the signature.

    Returns
    -------
    tuple[dict, JWTClaims]
        The header dict and the parsed claims.

    Raises
    ------
    JWTInvalidError
        If the token is malformed.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise JWTInvalidError("token must have three parts")

    try:
        header = json.loads(_b64url_decode(parts[0]))
        payload = json.loads(_b64url_decode(parts[1]))
    except (ValueError, json.JSONDecodeError) as exc:
        raise JWTInvalidError(f"invalid token encoding: {exc}") from exc

    return header, JWTClaims.from_dict(payload)


# ---------------------------------------------------------------------------
# JWT verification
# ---------------------------------------------------------------------------


def verify_jwt(
    token: str,
    *,
    secret: str | bytes,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
    subject: str | None = None,
    leeway: int = 0,
    verify_exp: bool = True,
    verify_nbf: bool = True,
) -> JWTClaims:
    """Verify a JWT token and return its claims.

    Parameters
    ----------
    token:
        The compact JWS string.
    secret:
        The HMAC secret.
    algorithm:
        Expected algorithm (only ``HS256`` supported).
    issuer:
        If provided, the token's ``iss`` claim must match.
    audience:
        If provided, the token's ``aud`` claim must match.
    subject:
        If provided, the token's ``sub`` claim must match.
    leeway:
        Clock-skew tolerance in seconds for exp/nbf checks.
    verify_exp:
        Whether to check the ``exp`` claim.
    verify_nbf:
        Whether to check the ``nbf`` claim.

    Returns
    -------
    JWTClaims
        The verified claims.

    Raises
    ------
    JWTInvalidError
        If the signature is invalid or the token is malformed.
    JWTExpiredError
        If the token has expired.
    JWTAlgorithmError
        If the algorithm is unsupported or mismatched.
    """
    if algorithm != "HS256":
        raise JWTAlgorithmError(f"unsupported algorithm: {algorithm}")

    parts = token.split(".")
    if len(parts) != 3:
        raise JWTInvalidError("token must have three parts")

    header_b64, payload_b64, sig_b64 = parts

    # Verify algorithm in header
    try:
        header = json.loads(_b64url_decode(header_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise JWTInvalidError(f"invalid header: {exc}") from exc

    if header.get("alg") != "HS256":
        raise JWTAlgorithmError(f"expected HS256, got {header.get('alg')!r}")

    # Verify signature
    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected_sig = _sign(signing_input, secret)
    try:
        actual_sig = _b64url_decode(sig_b64)
    except ValueError as exc:
        raise JWTInvalidError(f"invalid signature encoding: {exc}") from exc

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise JWTInvalidError("signature mismatch")

    # Parse claims
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise JWTInvalidError(f"invalid payload: {exc}") from exc

    claims = JWTClaims.from_dict(payload)
    now = time.time()

    # Check expiration
    if verify_exp and claims.exp is not None:
        if now >= claims.exp + leeway:
            raise JWTExpiredError("token has expired")

    # Check not-before
    if verify_nbf and claims.nbf is not None:
        if now < claims.nbf - leeway:
            raise JWTInvalidError("token is not yet valid")

    # Check issuer
    if issuer is not None and claims.iss != issuer:
        raise JWTInvalidError(f"expected issuer {issuer!r}, got {claims.iss!r}")

    # Check audience
    if audience is not None and claims.aud != audience:
        raise JWTInvalidError(f"expected audience {audience!r}, got {claims.aud!r}")

    # Check subject
    if subject is not None and claims.sub != subject:
        raise JWTInvalidError(f"expected subject {subject!r}, got {claims.sub!r}")

    return claims


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sign(signing_input: bytes, secret: str | bytes) -> bytes:
    """Produce an HMAC-SHA256 signature."""
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    return hmac.new(secret, signing_input, hashlib.sha256).digest()
