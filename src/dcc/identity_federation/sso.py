"""SSO connection management.

Manages SAML and OIDC SSO connections for identity federation.
Handles metadata parsing, certificate validation, and connection lifecycle.
"""
from __future__ import annotations

import hashlib
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from .models import (
    ProviderType,
    SSOConnection,
    SSOMetadataError,
)
from ..security.tenant import parse_tenant_id


# ---------------------------------------------------------------------------
# SAML metadata parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SAMLMetadata:
    """Parsed SAML 2.0 IdP metadata.

    Attributes
    ----------
    entity_id:
        The SAML entity identifier.
    sso_url:
        Single sign-on URL (HTTP-Redirect binding).
    slo_url:
        Single logout URL (optional).
    signing_certificates:
        List of base64-encoded X.509 signing certificates.
    name_id_format:
        Supported NameID formats.
    """

    entity_id: str
    sso_url: str = ""
    slo_url: str = ""
    signing_certificates: list[str] = field(default_factory=list)
    name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"


def parse_saml_metadata(xml_content: str) -> SAMLMetadata:
    """Parse SAML 2.0 IdP metadata XML.

    Parameters
    ----------
    xml_content:
        The raw XML metadata document.

    Returns
    -------
    SAMLMetadata
        The parsed metadata.

    Raises
    ------
    SSOMetadataError
        If the XML is invalid or missing required elements.
    """
    try:
        import xml.etree.ElementTree as ET
    except ImportError as exc:
        raise SSOMetadataError("XML parsing requires xml.etree.ElementTree") from exc

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise SSOMetadataError(f"invalid SAML metadata XML: {exc}") from exc

    # Handle namespaces
    ns = {
        "md": "urn:oasis:names:tc:SAML:2.0:metadata",
        "ds": "http://www.w3.org/2000/09/xmldsig#",
    }

    entity_id = root.get("entityID", "")
    if not entity_id:
        raise SSOMetadataError("SAML metadata missing entityID")

    # Find IDPSSODescriptor
    idp_descriptor = root.find(".//md:IDPSSODescriptor", ns)
    if idp_descriptor is None:
        raise SSOMetadataError("SAML metadata missing IDPSSODescriptor")

    # Extract SSO URL
    sso_url = ""
    sso_element = idp_descriptor.find(
        "md:SingleSignOnService[@Binding='urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect']",
        ns,
    )
    if sso_element is not None:
        sso_url = sso_element.get("Location", "")

    # Extract SLO URL
    slo_url = ""
    slo_element = idp_descriptor.find(
        "md:SingleLogoutService[@Binding='urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect']",
        ns,
    )
    if slo_element is not None:
        slo_url = slo_element.get("Location", "")

    # Extract signing certificates
    certs = []
    for cert_elem in idp_descriptor.findall(".//ds:X509Certificate", ns):
        if cert_elem.text:
            certs.append(cert_elem.text.strip())

    return SAMLMetadata(
        entity_id=entity_id,
        sso_url=sso_url,
        slo_url=slo_url,
        signing_certificates=certs,
    )


# ---------------------------------------------------------------------------
# OIDC discovery
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OIDCDiscoveryDocument:
    """Parsed OIDC discovery document.

    Attributes
    ----------
    issuer:
        The OIDC issuer URL.
    authorization_endpoint:
        Authorization endpoint URL.
    token_endpoint:
        Token endpoint URL.
    userinfo_endpoint:
        UserInfo endpoint URL.
    jwks_uri:
        JSON Web Key Set URL.
    scopes_supported:
        Supported scopes.
    response_types_supported:
        Supported response types.
    """

    issuer: str
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    userinfo_endpoint: str = ""
    jwks_uri: str = ""
    scopes_supported: list[str] = field(default_factory=list)
    response_types_supported: list[str] = field(default_factory=list)


def fetch_oidc_discovery(issuer_url: str) -> OIDCDiscoveryDocument:
    """Fetch and parse an OIDC discovery document.

    Parameters
    ----------
    issuer_url:
        The OIDC issuer URL (e.g. ``https://accounts.google.com``).

    Returns
    -------
    OIDCDiscoveryDocument
        The parsed discovery document.

    Raises
    ------
    SSOMetadataError
        If the discovery document cannot be fetched or parsed.
    """
    discovery_url = urllib.parse.urljoin(
        issuer_url.rstrip("/") + "/",
        ".well-known/openid-configuration",
    )

    try:
        request = urllib.request.Request(
            discovery_url,
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            import json
            data = json.loads(response.read().decode())
    except Exception as exc:
        raise SSOMetadataError(
            f"failed to fetch OIDC discovery from {discovery_url}: {exc}"
        ) from exc

    return OIDCDiscoveryDocument(
        issuer=data.get("issuer", issuer_url),
        authorization_endpoint=data.get("authorization_endpoint", ""),
        token_endpoint=data.get("token_endpoint", ""),
        userinfo_endpoint=data.get("userinfo_endpoint", ""),
        jwks_uri=data.get("jwks_uri", ""),
        scopes_supported=data.get("scopes_supported", []),
        response_types_supported=data.get("response_types_supported", []),
    )


# ---------------------------------------------------------------------------
# SSO connection manager
# ---------------------------------------------------------------------------


class SSOConnectionManager:
    """Manages SSO connections for identity federation.

    Provides CRUD operations for SSO connections and validates
    connection health.
    """

    def __init__(self) -> None:
        self._connections: dict[UUID, SSOConnection] = {}

    def create_connection(
        self,
        *,
        name: str,
        protocol: str,
        provider_type: ProviderType,
        entity_id: str = "",
        sso_url: str = "",
        slo_url: str = "",
        tenant_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> SSOConnection:
        """Create a new SSO connection.

        Parameters
        ----------
        name:
            Human-readable connection name.
        protocol:
            ``saml`` or ``oidc``.
        provider_type:
            The identity provider type.
        entity_id:
            SAML entity ID or OIDC issuer.
        sso_url:
            SSO endpoint URL.
        slo_url:
            Single logout URL (SAML only).
        tenant_id:
            The tenant this connection serves.
        metadata:
            Additional connection metadata.

        Returns
        -------
        SSOConnection
            The created connection.
        """
        conn = SSOConnection(
            id=uuid4(),
            name=name,
            protocol=protocol,
            provider_type=provider_type,
            entity_id=entity_id,
            sso_url=sso_url,
            slo_url=slo_url,
            tenant_id=tenant_id,
            metadata=metadata or {},
        )
        self._connections[conn.id] = conn
        return conn

    def get_connection(self, connection_id: UUID) -> SSOConnection:
        """Retrieve a connection by ID."""
        conn = self._connections.get(connection_id)
        if conn is None:
            raise SSOMetadataError(f"connection {connection_id} not found")
        return conn

    def list_connections(
        self,
        *,
        tenant_id: str = "",
        provider_type: Optional[ProviderType] = None,
    ) -> list[SSOConnection]:
        """List SSO connections, optionally filtered."""
        results = []
        for conn in self._connections.values():
            if tenant_id and conn.tenant_id != tenant_id:
                continue
            if provider_type and conn.provider_type != provider_type:
                continue
            results.append(conn)
        return results

    def update_connection(
        self,
        connection_id: UUID,
        **updates: Any,
    ) -> SSOConnection:
        """Update an existing connection."""
        conn = self.get_connection(connection_id)
        # Create updated connection (dataclass is mutable via slots)
        for key, value in updates.items():
            if hasattr(conn, key):
                object.__setattr__(conn, key, value)
        return conn

    def delete_connection(self, connection_id: UUID) -> None:
        """Delete an SSO connection."""
        self._connections.pop(connection_id, None)

    def validate_connection(self, connection_id: UUID) -> dict[str, Any]:
        """Validate an SSO connection's configuration.

        Returns
        -------
        dict
            Validation results with ``valid`` (bool) and ``errors`` (list).
        """
        conn = self.get_connection(connection_id)
        errors: list[str] = []

        if not conn.entity_id:
            errors.append("entity_id is required")
        if not conn.sso_url:
            errors.append("sso_url is required")
        if conn.protocol == "saml" and not conn.signing_certificates:
            errors.append("SAML connection requires at least one signing certificate")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "connection_id": str(connection_id),
        }

    def compute_certificate_fingerprint(
        self,
        certificate_b64: str,
        algorithm: str = "sha256",
    ) -> str:
        """Compute a fingerprint for a base64-encoded certificate.

        Parameters
        ----------
        certificate_b64:
            Base64-encoded X.509 certificate.
        algorithm:
            Hash algorithm (``sha256`` or ``sha1``).

        Returns
        -------
        str
            The hex-encoded fingerprint.
        """
        import base64
        cert_bytes = base64.b64decode(certificate_b64)
        if algorithm == "sha256":
            return hashlib.sha256(cert_bytes).hexdigest()
        elif algorithm == "sha1":
            return hashlib.sha1(cert_bytes).hexdigest()
        else:
            raise ValueError(f"unsupported hash algorithm: {algorithm}")
