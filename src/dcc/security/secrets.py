"""Secret management integration for Data Center Commander.

Provides bounded, read-only access to HashiCorp Vault and AWS Secrets Manager.
All operations are read-only, never persist secrets, and never expose secret
values in logs or error messages.

Contract/design only — no live secret manager integration is certified.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RESPONSE_BYTES = 2_000_000
MAX_SECRETS_PER_LIST = 200
DEFAULT_TIMEOUT_S = 8
USER_AGENT = "DataCenterCommander-Secrets/0.1"

# Vault defaults
DEFAULT_VAULT_MOUNT = "secret"
DEFAULT_VAULT_API_VERSION = "v1"

# AWS defaults
DEFAULT_AWS_REGION = "us-east-1"
AWS_SECRETS_MANAGER_ENDPOINT = "https://secretsmanager.{region}.amazonaws.com"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SecretValue:
    """A single secret key-value pair.

    The value is held in memory only and never logged or persisted.
    """
    key: str
    value: str

    def __repr__(self) -> str:
        return f"SecretValue(key={self.key!r}, value='***')"


@dataclass(slots=True)
class SecretEntry:
    """Metadata about a secret stored in a secrets manager.

    Does not contain the secret value itself.
    """
    name: str
    path: str
    version: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class VaultConfig:
    """Configuration for a HashiCorp Vault adapter instance."""
    endpoint: str
    token_ref: str | None = None
    namespace: str | None = None
    mount_point: str = DEFAULT_VAULT_MOUNT
    api_version: str = DEFAULT_VAULT_API_VERSION
    timeout_s: float = DEFAULT_TIMEOUT_S
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AWSSecretsManagerConfig:
    """Configuration for an AWS Secrets Manager adapter instance."""
    region: str = DEFAULT_AWS_REGION
    credential_ref: str | None = None
    timeout_s: float = DEFAULT_TIMEOUT_S
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class SecretsProviderProtocol(Protocol):
    """Protocol that concrete secrets manager adapters should implement."""
    name: str
    version: str

    def health_check(self) -> bool: ...
    def get_secret(self, path: str, *, version: int | None = None) -> list[SecretValue]: ...
    def list_secrets(self, path: str = "") -> list[SecretEntry]: ...


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_secret_path(path: str) -> str:
    """Validate a secret path (Vault path or AWS secret name/ARN)."""
    path = path.strip()
    if not path:
        raise ValueError("secret path is required")
    if len(path) > 512:
        raise ValueError("secret path exceeds 512 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", path):
        raise ValueError("secret path contains unsupported characters")
    return path


def _validate_secret_name(name: str) -> str:
    """Validate a secret name."""
    name = name.strip()
    if not name:
        raise ValueError("secret name is required")
    if len(name) > 256:
        raise ValueError("secret name exceeds 256 characters")
    if not re.fullmatch(r"[A-Za-z0-9._:/-]+", name):
        raise ValueError("secret name contains unsupported characters")
    return name


def _validate_version(version: int | None) -> int | None:
    """Validate a secret version number."""
    if version is None:
        return None
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise ValueError("version must be a non-negative integer")
    return version


def _safe_int(value: Any) -> int | None:
    """Safely convert a value to int."""
    if value is None:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _http_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """Perform a bounded HTTP request and return parsed JSON.

    Never follows redirects. Never includes secret values in error messages.
    """
    request_headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        url, headers=request_headers, method=method, data=data
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ConnectionError(
                f"Response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB safety limit"
            )
        payload = json.loads(raw or b"{}")
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(f"Unavailable ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ConnectionError("Invalid JSON response") from None
    if not isinstance(payload, dict):
        raise ConnectionError("Response did not match expected contract")
    return payload


# ---------------------------------------------------------------------------
# HashiCorp Vault adapter
# ---------------------------------------------------------------------------

class VaultAdapter:
    """Read-only HashiCorp Vault adapter.

    Supports KV v2 secrets engine. Never writes to or deletes secrets.
    All operations are bounded and read-only.
    """

    name = "hashicorp-vault"
    version = "0.1.0"

    def __init__(self, config: VaultConfig) -> None:
        self.config = config
        self._last_health_check: dt.datetime | None = None
        self._consecutive_failures: int = 0

    # -- Health -------------------------------------------------------------

    def health_check(self) -> bool:
        """Verify Vault endpoint is reachable and responsive."""
        try:
            url = f"{self.config.endpoint.rstrip('/')}/v1/sys/health"
            _http_request(url, timeout=self.config.timeout_s)
            self._consecutive_failures = 0
            self._last_health_check = dt.datetime.now(dt.timezone.utc)
            return True
        except Exception:
            self._consecutive_failures += 1
            return False

    # -- Secret operations --------------------------------------------------

    def get_secret(
        self,
        path: str,
        *,
        version: int | None = None,
    ) -> list[SecretValue]:
        """Read a secret from Vault (KV v2).

        Args:
            path: Secret path (e.g., "my-app/database").
            version: Optional specific version to read.

        Returns:
            List of SecretValue objects (key-value pairs).

        Raises:
            ValueError: If path or version is invalid.
            ConnectionError: If Vault is unavailable or returns an error.
        """
        path = _validate_secret_path(path)
        version = _validate_version(version)

        # Build URL for KV v2 read
        # KV v2 paths are: {mount}/data/{path}
        encoded_path = urllib.parse.quote(path, safe="/")
        url = (
            f"{self.config.endpoint.rstrip('/')}/{self.config.api_version}"
            f"/{self.config.mount_point}/data/{encoded_path}"
        )
        if version is not None:
            url = f"{url}?{urllib.parse.urlencode({'version': version})}"

        headers = self._auth_headers()
        payload = _http_request(url, headers=headers, timeout=self.config.timeout_s)

        return self._parse_secret_payload(payload)

    def _parse_secret_payload(self, payload: dict[str, Any]) -> list[SecretValue]:
        """Parse Vault KV v2 response into SecretValue objects."""
        data = payload.get("data", {})
        if not isinstance(data, dict):
            return []

        # KV v2 wraps actual secret data under "data" key
        inner_data = data.get("data", {})
        if not isinstance(inner_data, dict):
            return []

        results: list[SecretValue] = []
        for key, value in inner_data.items():
            if not isinstance(key, str) or not key.strip():
                continue
            if value is None:
                continue
            # Convert value to string (Vault stores strings)
            str_value = str(value) if not isinstance(value, str) else value
            results.append(SecretValue(key=key, value=str_value))
        return results

    def list_secrets(self, path: str = "") -> list[SecretEntry]:
        """List secrets under a path prefix (KV v2 list operation).

        Args:
            path: Path prefix to list (empty lists root of mount).

        Returns:
            List of SecretEntry objects (metadata only, no values).
        """
        path = path.strip()
        if path and not re.fullmatch(r"[A-Za-z0-9._:/-]*", path):
            raise ValueError("path contains unsupported characters")

        # KV v2 list: {mount}/metadata/{path}?list=true
        encoded_path = urllib.parse.quote(path, safe="/")
        url = (
            f"{self.config.endpoint.rstrip('/')}/{self.config.api_version}"
            f"/{self.config.mount_point}/metadata/{encoded_path}"
            f"?{urllib.parse.urlencode({'list': 'true'})}"
        )

        headers = self._auth_headers()
        payload = _http_request(url, headers=headers, timeout=self.config.timeout_s)

        return self._parse_list_payload(payload, path)

    def _parse_list_payload(
        self, payload: dict[str, Any], base_path: str
    ) -> list[SecretEntry]:
        """Parse Vault list response into SecretEntry objects."""
        data = payload.get("data", {})
        if not isinstance(data, dict):
            return []

        keys = data.get("keys", [])
        if not isinstance(keys, list):
            return []

        results: list[SecretEntry] = []
        for key in keys:
            if not isinstance(key, str) or not key.strip():
                continue
            full_path = f"{base_path}/{key}" if base_path else key
            results.append(SecretEntry(
                name=key,
                path=full_path,
            ))
            if len(results) >= MAX_SECRETS_PER_LIST:
                break
        return results

    # -- Internal helpers ---------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        """Build authentication headers for Vault requests.

        Token is read from environment variable referenced by token_ref,
        or from VAULT_TOKEN environment variable. Never includes the token
        in error messages or logs.
        """
        headers: dict[str, str] = {}
        token = self._resolve_token()
        if token:
            headers["X-Vault-Token"] = token
        if self.config.namespace:
            headers["X-Vault-Namespace"] = self.config.namespace
        return headers

    def _resolve_token(self) -> str | None:
        """Resolve Vault token from environment.

        Checks token_ref first, then VAULT_TOKEN env var.
        """
        if self.config.token_ref:
            token = os.environ.get(self.config.token_ref, "").strip()
            if token:
                return token
        return os.environ.get("VAULT_TOKEN", "").strip() or None

    # -- Snapshot / reporting ------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a full snapshot of the adapter state (no secret values)."""
        return {
            "name": self.name,
            "version": self.version,
            "endpoint": self.config.endpoint,
            "mount_point": self.config.mount_point,
            "api_version": self.config.api_version,
            "namespace": self.config.namespace,
            "timeout_s": self.config.timeout_s,
            "last_health_check": (
                self._last_health_check.isoformat()
                if self._last_health_check
                else None
            ),
            "consecutive_failures": self._consecutive_failures,
            "metadata": self.config.metadata,
            "persisted": False,
            "execution_permitted": False,
        }


# ---------------------------------------------------------------------------
# AWS Secrets Manager adapter
# ---------------------------------------------------------------------------

class AWSSecretsManagerAdapter:
    """Read-only AWS Secrets Manager adapter.

    Uses the AWS JSON 1.1 protocol over HTTPS. Never writes or deletes secrets.
    All operations are bounded and read-only.
    """

    name = "aws-secrets-manager"
    version = "0.1.0"

    def __init__(self, config: AWSSecretsManagerConfig) -> None:
        self.config = config
        self._last_health_check: dt.datetime | None = None
        self._consecutive_failures: int = 0

    # -- Health -------------------------------------------------------------

    def health_check(self) -> bool:
        """Verify AWS Secrets Manager endpoint is reachable."""
        try:
            # Use ListSecrets with MaxResults=1 as a minimal health check
            url = self._endpoint_url()
            self._post_request(url, {"MaxResults": 1})
            self._consecutive_failures = 0
            self._last_health_check = dt.datetime.now(dt.timezone.utc)
            return True
        except Exception:
            self._consecutive_failures += 1
            return False

    # -- Secret operations --------------------------------------------------

    def get_secret(
        self,
        path: str,
        *,
        version: int | None = None,
    ) -> list[SecretValue]:
        """Read a secret from AWS Secrets Manager.

        Args:
            path: Secret name or ARN.
            version: Ignored (AWS uses version stages, not numbers).

        Returns:
            List of SecretValue objects (key-value pairs).

        Raises:
            ValueError: If path is invalid.
            ConnectionError: If AWS Secrets Manager is unavailable.
        """
        path = _validate_secret_path(path)

        url = self._endpoint_url()
        body: dict[str, Any] = {"SecretId": path}
        if version is not None:
            # AWS uses version stage labels, not numbers
            # We accept version as a convenience but map to VersionStage
            body["VersionStage"] = f"version-{version}"

        payload = self._post_request(url, body)
        return self._parse_secret_payload(payload)

    def _parse_secret_payload(self, payload: dict[str, Any]) -> list[SecretValue]:
        """Parse AWS Secrets Manager response into SecretValue objects."""
        secret_string = payload.get("SecretString")
        if not secret_string:
            return []

        # SecretString is typically a JSON string
        try:
            parsed = json.loads(secret_string)
        except (json.JSONDecodeError, TypeError):
            # If not JSON, treat the whole string as a single value
            return [SecretValue(key="SecretString", value=str(secret_string))]

        if not isinstance(parsed, dict):
            return [SecretValue(key="SecretString", value=str(parsed))]

        results: list[SecretValue] = []
        for key, value in parsed.items():
            if not isinstance(key, str) or not key.strip():
                continue
            if value is None:
                continue
            str_value = str(value) if not isinstance(value, str) else value
            results.append(SecretValue(key=key, value=str_value))
        return results

    def list_secrets(self, path: str = "") -> list[SecretEntry]:
        """List secrets in AWS Secrets Manager.

        Args:
            path: Ignored (AWS doesn't support path-based listing).
                Kept for protocol compatibility.

        Returns:
            List of SecretEntry objects (metadata only, no values).
        """
        url = self._endpoint_url()
        body: dict[str, Any] = {"MaxResults": MAX_SECRETS_PER_LIST}

        payload = self._post_request(url, body)
        return self._parse_list_payload(payload)

    def _parse_list_payload(self, payload: dict[str, Any]) -> list[SecretEntry]:
        """Parse AWS Secrets Manager list response into SecretEntry objects."""
        secrets = payload.get("SecretList", [])
        if not isinstance(secrets, list):
            return []

        results: list[SecretEntry] = []
        for item in secrets:
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name", "")).strip()
            if not name:
                continue
            created_date = item.get("CreatedDate")
            last_changed = item.get("LastChangedDate")
            results.append(SecretEntry(
                name=name,
                path=name,
                created_at=created_date.isoformat() if isinstance(created_date, dt.datetime) else None,
                updated_at=last_changed.isoformat() if isinstance(last_changed, dt.datetime) else None,
                metadata={
                    "description": str(item.get("Description", "")),
                    "arn": str(item.get("ARN", "")),
                },
            ))
            if len(results) >= MAX_SECRETS_PER_LIST:
                break
        return results

    # -- Internal helpers ---------------------------------------------------

    def _endpoint_url(self) -> str:
        """Build the AWS Secrets Manager endpoint URL."""
        return AWS_SECRETS_MANAGER_ENDPOINT.format(region=self.config.region)

    def _post_request(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request to AWS Secrets Manager.

        Uses AWS JSON 1.1 protocol. Authentication is handled by the
        credential_ref environment variable (access key) or IAM role.
        """
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "secretsmanager.ListSecrets",
        }

        # Determine target from body
        if "SecretId" in body:
            headers["X-Amz-Target"] = "secretsmanager.GetSecretValue"
        elif "MaxResults" in body:
            headers["X-Amz-Target"] = "secretsmanager.ListSecrets"

        data = json.dumps(body).encode("utf-8")

        # Resolve credentials from environment
        access_key = self._resolve_access_key()
        if access_key:
            headers["Authorization"] = f"AWS4-HMAC-SHA256 Credential={access_key}"

        return _http_request(
            url,
            method="POST",
            headers=headers,
            data=data,
            timeout=self.config.timeout_s,
        )

    def _resolve_access_key(self) -> str | None:
        """Resolve AWS access key from environment.

        Checks credential_ref first, then AWS_ACCESS_KEY_ID env var.
        """
        if self.config.credential_ref:
            key = os.environ.get(self.config.credential_ref, "").strip()
            if key:
                return key
        return os.environ.get("AWS_ACCESS_KEY_ID", "").strip() or None

    # -- Snapshot / reporting ------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a full snapshot of the adapter state (no secret values)."""
        return {
            "name": self.name,
            "version": self.version,
            "region": self.config.region,
            "endpoint": self._endpoint_url(),
            "timeout_s": self.config.timeout_s,
            "last_health_check": (
                self._last_health_check.isoformat()
                if self._last_health_check
                else None
            ),
            "consecutive_failures": self._consecutive_failures,
            "metadata": self.config.metadata,
            "persisted": False,
            "execution_permitted": False,
        }


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def create_vault_adapter(
    endpoint: str,
    *,
    token_ref: str | None = None,
    namespace: str | None = None,
    mount_point: str = DEFAULT_VAULT_MOUNT,
    api_version: str = DEFAULT_VAULT_API_VERSION,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    metadata: dict[str, Any] | None = None,
) -> VaultAdapter:
    """Factory function to create a configured Vault adapter.

    Args:
        endpoint: Vault server URL (e.g., "https://vault.example.com:8200").
        token_ref: Environment variable name containing the Vault token.
        namespace: Vault namespace (for Vault Enterprise).
        mount_point: KV v2 mount point (default: "secret").
        api_version: API version path prefix (default: "v1").
        timeout_s: Request timeout in seconds.
        metadata: Additional metadata for the adapter.

    Returns:
        Configured VaultAdapter instance.

    Raises:
        ValueError: If endpoint or configuration is invalid.
    """
    if not endpoint or not endpoint.startswith("https://"):
        raise ValueError("endpoint must be an HTTPS URL")
    if len(endpoint) > 2048:
        raise ValueError("endpoint URL is too long")
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", api_version):
        raise ValueError("api_version contains unsupported characters")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", mount_point):
        raise ValueError("mount_point contains unsupported characters")
    if timeout_s < 0.5 or timeout_s > 60:
        raise ValueError("timeout_s must be 0.5-60")

    config = VaultConfig(
        endpoint=endpoint,
        token_ref=token_ref,
        namespace=namespace,
        mount_point=mount_point,
        api_version=api_version,
        timeout_s=timeout_s,
        metadata=metadata or {},
    )
    return VaultAdapter(config)


def create_aws_secrets_manager_adapter(
    region: str = DEFAULT_AWS_REGION,
    *,
    credential_ref: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    metadata: dict[str, Any] | None = None,
) -> AWSSecretsManagerAdapter:
    """Factory function to create a configured AWS Secrets Manager adapter.

    Args:
        region: AWS region (default: "us-east-1").
        credential_ref: Environment variable name containing the AWS access key.
        timeout_s: Request timeout in seconds.
        metadata: Additional metadata for the adapter.

    Returns:
        Configured AWSSecretsManagerAdapter instance.

    Raises:
        ValueError: If region or configuration is invalid.
    """
    if not region or len(region) > 64:
        raise ValueError("region is required and must be at most 64 characters")
    if not re.fullmatch(r"[a-z]{2}-[a-z]+-\d+", region):
        raise ValueError("region must be a valid AWS region format (e.g., us-east-1)")
    if timeout_s < 0.5 or timeout_s > 60:
        raise ValueError("timeout_s must be 0.5-60")

    config = AWSSecretsManagerConfig(
        region=region,
        credential_ref=credential_ref,
        timeout_s=timeout_s,
        metadata=metadata or {},
    )
    return AWSSecretsManagerAdapter(config)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "AWSSecretsManagerAdapter",
    "AWSSecretsManagerConfig",
    "SecretEntry",
    "SecretValue",
    "SecretsProviderProtocol",
    "VaultAdapter",
    "VaultConfig",
    "create_aws_secrets_manager_adapter",
    "create_vault_adapter",
]
