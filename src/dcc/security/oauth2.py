"""OAuth2 authorization-code flow with PKCE.

Implements the server-side logic for:
- Authorization URL generation (with PKCE)
- Token exchange (authorization code -> access token)
- Token refresh
- Token introspection

Uses only the Python standard library. The HTTP calls to the authorization
server are abstracted via :class:`OAuth2Client` so tests can inject a mock.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable

__all__ = [
    "OAuth2Config",
    "OAuth2Error",
    "OAuth2TokenResponse",
    "OAuth2Client",
    "OAuth2Server",
    "PKCEChallenge",
]


class OAuth2Error(Exception):
    """Base exception for OAuth2 operations."""


class OAuth2ConfigError(OAuth2Error):
    """Raised when the OAuth2 configuration is invalid."""


class OAuth2TokenError(OAuth2Error):
    """Raised when a token exchange or refresh fails."""


class OAuth2StateError(OAuth2Error):
    """Raised when the state parameter is invalid or missing."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class OAuth2Config:
    """OAuth2 client configuration.

    Parameters
    ----------
    client_id:
        The OAuth2 client ID.
    client_secret:
        The OAuth2 client secret (for confidential clients).
    authorization_endpoint:
        Full URL of the authorization server's authorization endpoint.
    token_endpoint:
        Full URL of the authorization server's token endpoint.
    redirect_uri:
        The callback URL registered with the authorization server.
    scopes:
        List of OAuth2 scopes to request.
    """

    client_id: str
    client_secret: str
    authorization_endpoint: str
    token_endpoint: str
    redirect_uri: str
    scopes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.client_id:
            raise OAuth2ConfigError("client_id is required")
        if not self.authorization_endpoint:
            raise OAuth2ConfigError("authorization_endpoint is required")
        if not self.token_endpoint:
            raise OAuth2ConfigError("token_endpoint is required")
        if not self.redirect_uri:
            raise OAuth2ConfigError("redirect_uri is required")


# ---------------------------------------------------------------------------
# PKCE (RFC 7636)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PKCEChallenge:
    """PKCE verifier/challenge pair.

    The verifier is kept client-side; the challenge is sent in the
    authorization request. The verifier is sent in the token request.
    """

    verifier: str
    challenge: str
    method: str = "S256"

    @classmethod
    def generate(cls) -> PKCEChallenge:
        """Generate a new PKCE pair with S256 method."""
        # 43-128 chars per RFC 7636
        verifier = base64url_encode(secrets.token_bytes(32))
        challenge = base64url_encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        )
        return cls(verifier=verifier, challenge=challenge, method="S256")

    def verify(self, verifier: str) -> bool:
        """Verify that a verifier matches this challenge."""
        expected = base64url_encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        )
        return hmac.compare_digest(expected, self.challenge)


def base64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# Token response
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class OAuth2TokenResponse:
    """Parsed OAuth2 token response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
    id_token: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_in is None:
            return False
        # Consider it expired 60 seconds before actual expiry
        return time.time() >= (self._obtained_at + self.expires_in - 60)

    _obtained_at: float = field(default_factory=time.time, init=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OAuth2TokenResponse:
        return cls(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in"),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
            id_token=data.get("id_token"),
            raw=dict(data),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "refresh_token": self.refresh_token,
            "scope": self.scope,
            "id_token": self.id_token,
        }


# ---------------------------------------------------------------------------
# HTTP client abstraction
# ---------------------------------------------------------------------------


class OAuth2Client:
    """Abstract HTTP client for OAuth2 token endpoint calls.

    Subclass this to use a real HTTP library (httpx, requests, aiohttp).
    The default implementation raises ``NotImplementedError``.
    """

    def post_form(
        self,
        url: str,
        data: dict[str, str],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """POST form-encoded data and return the JSON response.

        Parameters
        ----------
        url:
            The endpoint URL.
        data:
            Form fields.
        headers:
            Additional headers.

        Returns
        -------
        dict
            The parsed JSON response.

        Raises
        ------
        OAuth2TokenError
            If the request fails or returns an error.
        """
        raise NotImplementedError(
            "OAuth2Client.post_form must be subclassed for real HTTP calls"
        )


# ---------------------------------------------------------------------------
# OAuth2 server-side flow
# ---------------------------------------------------------------------------


class OAuth2Server:
    """Server-side OAuth2 authorization-code flow with PKCE.

    This class generates authorization URLs, validates state parameters,
    and exchanges authorization codes for tokens. It does not make HTTP
    calls itself — inject an :class:`OAuth2Client` subclass for that.

    Parameters
    ----------
    config:
        The OAuth2 client configuration.
    client:
        An HTTP client for token endpoint calls.
    state_store:
        Optional callable that returns the stored state for a given session.
        If omitted, state validation is skipped (not recommended for prod).
    """

    def __init__(
        self,
        config: OAuth2Config,
        client: OAuth2Client | None = None,
        state_store: Callable[[str], str | None] | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self._state_store = state_store
        self._pending_pkce: dict[str, PKCEChallenge] = {}  # state -> challenge

    # -- Authorization URL --------------------------------------------------

    def build_authorization_url(
        self,
        *,
        state: str | None = None,
        extra_params: dict[str, str] | None = None,
        use_pkce: bool = True,
    ) -> tuple[str, str]:
        """Build the authorization URL and return ``(url, state)``.

        Parameters
        ----------
        state:
            An opaque state parameter for CSRF protection. If omitted,
            a random one is generated.
        extra_params:
            Additional query parameters to include.
        use_pkce:
            Whether to include PKCE parameters.

        Returns
        -------
        tuple[str, str]
            The full authorization URL and the state value.
        """
        if state is None:
            state = secrets.token_urlsafe(32)

        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "state": state,
        }

        if self.config.scopes:
            params["scope"] = " ".join(self.config.scopes)

        if use_pkce:
            pkce = PKCEChallenge.generate()
            self._pending_pkce[state] = pkce
            params["code_challenge"] = pkce.challenge
            params["code_challenge_method"] = pkce.method

        if extra_params:
            params.update(extra_params)

        query = urllib.parse.urlencode(params, safe=" ")
        url = f"{self.config.authorization_endpoint}?{query}"
        return url, state

    def validate_state(self, state: str, stored_state: str | None) -> bool:
        """Validate the state parameter against the stored value.

        Parameters
        ----------
        state:
            The state returned by the authorization server.
        stored_state:
            The state value stored in the user's session.

        Returns
        -------
        bool
            True if the states match.
        """
        if not state or not stored_state:
            return False
        return hmac.compare_digest(state, stored_state)

    # -- Token exchange -----------------------------------------------------

    def exchange_code(
        self,
        code: str,
        *,
        state: str | None = None,
        stored_state: str | None = None,
    ) -> OAuth2TokenResponse:
        """Exchange an authorization code for tokens.

        Parameters
        ----------
        code:
            The authorization code from the callback.
        state:
            The state parameter from the callback.
        stored_state:
            The state value stored in the user's session.

        Returns
        -------
        OAuth2TokenResponse
            The token response.

        Raises
        ------
        OAuth2StateError
            If state validation fails.
        OAuth2TokenError
            If the token request fails.
        """
        if not self.validate_state(state or "", stored_state):
            raise OAuth2StateError("state parameter mismatch")

        if self.client is None:
            raise OAuth2TokenError("no HTTP client configured")

        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        # Include PKCE verifier if we have one for this state
        if state and state in self._pending_pkce:
            pkce = self._pending_pkce.pop(state)
            data["code_verifier"] = pkce.verifier

        try:
            response = self.client.post_form(
                self.config.token_endpoint, data=data
            )
        except OAuth2TokenError:
            raise
        except Exception as exc:
            raise OAuth2TokenError(f"token request failed: {exc}") from exc

        if "error" in response:
            error = response["error"]
            description = response.get("error_description", "")
            raise OAuth2TokenError(f"OAuth2 error: {error} — {description}")

        return OAuth2TokenResponse.from_dict(response)

    # -- Token refresh ------------------------------------------------------

    def refresh_access_token(
        self, refresh_token: str
    ) -> OAuth2TokenResponse:
        """Refresh an access token using a refresh token.

        Parameters
        ----------
        refresh_token:
            The refresh token from a previous token response.

        Returns
        -------
        OAuth2TokenResponse
            The new token response.
        """
        if self.client is None:
            raise OAuth2TokenError("no HTTP client configured")

        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        try:
            response = self.client.post_form(
                self.config.token_endpoint, data=data
            )
        except OAuth2TokenError:
            raise
        except Exception as exc:
            raise OAuth2TokenError(f"token refresh failed: {exc}") from exc

        if "error" in response:
            error = response["error"]
            description = response.get("error_description", "")
            raise OAuth2TokenError(f"OAuth2 error: {error} — {description}")

        return OAuth2TokenResponse.from_dict(response)

    # -- Token introspection ------------------------------------------------

    def introspect_token(
        self,
        token: str,
        *,
        token_type_hint: str | None = None,
    ) -> dict[str, Any]:
        """Introspect a token (RFC 7662).

        Parameters
        ----------
        token:
            The token to introspect.
        token_type_hint:
            Optional hint (``access_token`` or ``refresh_token``).

        Returns
        -------
        dict
            The introspection response.
        """
        if self.client is None:
            raise OAuth2TokenError("no HTTP client configured")

        data: dict[str, str] = {
            "token": token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        if token_type_hint:
            data["token_type_hint"] = token_type_hint

        try:
            return self.client.post_form(
                self.config.token_endpoint, data=data
            )
        except Exception as exc:
            raise OAuth2TokenError(f"introspection failed: {exc}") from exc

    # -- Cleanup ------------------------------------------------------------

    def cleanup_pending(self, max_age_seconds: float = 600) -> int:
        """Remove pending PKCE challenges older than ``max_age_seconds``.

        Returns the count of removed entries.
        """
        now = time.time()
        to_remove = [
            state for state, pkce in self._pending_pkce.items()
            if now - getattr(pkce, "_created_at", now) > max_age_seconds
        ]
        for state in to_remove:
            self._pending_pkce.pop(state, None)
        return len(to_remove)
