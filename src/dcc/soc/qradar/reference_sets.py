"""QRadar reference set mappings for data center security.

Provides reference set definitions that can be imported into QRadar to
enrich offense and event data with data center context. Reference sets
include known data center IP ranges, asset classifications, threat
indicators, and compliance tags.

Contract/design only — no live QRadar integration is certified.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Reference set types
# ---------------------------------------------------------------------------

class ReferenceSetType(str, Enum):
    """Type of reference set."""
    IP = "IP"
    ALNUM = "ALNUM"
    ALNUM_IC = "ALNUM_IC"
    NUM = "NUM"
    PORT = "PORT"
    DATE = "DATE"


class ReferenceSetDataType(str, Enum):
    """Data type of reference set elements."""
    STRING = "string"
    INTEGER = "integer"
    IP = "ip"
    DATE = "date"


# ---------------------------------------------------------------------------
# Reference set models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ReferenceSetEntry:
    """A single entry in a reference set."""
    value: str
    source: str = "dcc"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "description": self.description,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReferenceSetEntry:
        return cls(
            value=str(data["value"]),
            source=str(data.get("source", "dcc")),
            description=str(data.get("description", "")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(slots=True)
class QRadarReferenceSetDefinition:
    """A complete QRadar reference set definition."""
    set_id: str
    name: str
    set_type: ReferenceSetType
    data_type: ReferenceSetDataType
    description: str = ""
    entries: list[ReferenceSetEntry] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "set_id": self.set_id,
            "name": self.name,
            "set_type": self.set_type.value,
            "data_type": self.data_type.value,
            "description": self.description,
            "entries": [e.to_dict() for e in self.entries],
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    def to_qradar_json(self) -> str:
        """Export as QRadar-compatible reference set JSON."""
        qradar_format = {
            "name": self.name,
            "element_type": self.set_type.value,
            "data_type": self.data_type.value,
            "description": self.description,
            "entries": [
                {
                    "value": e.value,
                    "source": e.source,
                    "description": e.description,
                }
                for e in self.entries
            ],
        }
        return json.dumps(qradar_format, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRadarReferenceSetDefinition:
        """Reconstruct from dictionary."""
        return cls(
            set_id=str(data["set_id"]),
            name=str(data.get("name", "")),
            set_type=ReferenceSetType(data.get("set_type", "ALNUM")),
            data_type=ReferenceSetDataType(data.get("data_type", "string")),
            description=str(data.get("description", "")),
            entries=[ReferenceSetEntry.from_dict(e) for e in data.get("entries", [])],
            tags=list(data.get("tags", [])),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Pre-built data center reference sets
# ---------------------------------------------------------------------------

def get_data_center_reference_sets() -> list[QRadarReferenceSetDefinition]:
    """Return the default set of data center reference sets for QRadar."""
    return [
        # Reference Set 1: Data Center IP Ranges
        QRadarReferenceSetDefinition(
            set_id="dcc-ip-ranges",
            name="DCC: Data Center IP Ranges",
            set_type=ReferenceSetType.IP,
            data_type=ReferenceSetDataType.IP,
            description="Known IP ranges for data center infrastructure including servers, storage, and network devices.",
            entries=[
                ReferenceSetEntry(value="10.0.0.0/8", source="dcc", description="RFC1918 private range for data center"),
                ReferenceSetEntry(value="172.16.0.0/12", source="dcc", description="RFC1918 private range for data center"),
                ReferenceSetEntry(value="192.168.0.0/16", source="dcc", description="RFC1918 private range for data center"),
            ],
            tags=["network", "ip-ranges", "dcc"],
        ),
        # Reference Set 2: Critical Assets
        QRadarReferenceSetDefinition(
            set_id="dcc-critical-assets",
            name="DCC: Critical Asset Hostnames",
            set_type=ReferenceSetType.ALNUM,
            data_type=ReferenceSetDataType.STRING,
            description="Hostnames of critical data center assets requiring enhanced monitoring.",
            entries=[
                ReferenceSetEntry(value="dc-core-router-01", source="dcc", description="Core network router"),
                ReferenceSetEntry(value="dc-core-router-02", source="dcc", description="Core network router backup"),
                ReferenceSetEntry(value="dc-storage-primary", source="dcc", description="Primary storage array"),
                ReferenceSetEntry(value="dc-storage-backup", source="dcc", description="Backup storage array"),
                ReferenceSetEntry(value="dc-db-primary", source="dcc", description="Primary database server"),
                ReferenceSetEntry(value="dc-db-replica", source="dcc", description="Database replica server"),
                ReferenceSetEntry(value="dc-app-server-01", source="dcc", description="Application server cluster node 1"),
                ReferenceSetEntry(value="dc-app-server-02", source="dcc", description="Application server cluster node 2"),
            ],
            tags=["assets", "critical", "dcc"],
        ),
        # Reference Set 3: Threat Indicators
        QRadarReferenceSetDefinition(
            set_id="dcc-threat-indicators",
            name="DCC: Known Threat Indicators",
            set_type=ReferenceSetType.ALNUM,
            data_type=ReferenceSetDataType.STRING,
            description="Known malicious IPs, domains, and file hashes from threat intelligence feeds.",
            entries=[
                ReferenceSetEntry(value="192.0.2.100", source="dcc", description="Known C2 server"),
                ReferenceSetEntry(value="192.0.2.101", source="dcc", description="Known C2 server"),
                ReferenceSetEntry(value="203.0.113.50", source="dcc", description="Known phishing domain"),
                ReferenceSetEntry(value="evil-malware.example.com", source="dcc", description="Known malware distribution domain"),
                ReferenceSetEntry(value="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2", source="dcc", description="Known malware hash"),
            ],
            tags=["threat-intel", "ioc", "dcc"],
        ),
        # Reference Set 4: Compliance Tags
        QRadarReferenceSetDefinition(
            set_id="dcc-compliance-tags",
            name="DCC: Compliance Classification Tags",
            set_type=ReferenceSetType.ALNUM,
            data_type=ReferenceSetDataType.STRING,
            description="Data classification and compliance tags for data center assets.",
            entries=[
                ReferenceSetEntry(value="pci-dss-scope", source="dcc", description="Asset in PCI-DSS scope"),
                ReferenceSetEntry(value="hipaa-scope", source="dcc", description="Asset in HIPAA scope"),
                ReferenceSetEntry(value="sox-scope", source="dcc", description="Asset in SOX scope"),
                ReferenceSetEntry(value="confidential", source="dcc", description="Confidential data classification"),
                ReferenceSetEntry(value="restricted", source="dcc", description="Restricted data classification"),
                ReferenceSetEntry(value="public", source="dcc", description="Public data classification"),
            ],
            tags=["compliance", "classification", "dcc"],
        ),
        # Reference Set 5: Suspicious Ports
        QRadarReferenceSetDefinition(
            set_id="dcc-suspicious-ports",
            name="DCC: Suspicious Port Numbers",
            set_type=ReferenceSetType.PORT,
            data_type=ReferenceSetDataType.INTEGER,
            description="Port numbers commonly associated with malicious activity or unauthorized services.",
            entries=[
                ReferenceSetEntry(value="4444", source="dcc", description="Metasploit default"),
                ReferenceSetEntry(value="5555", source="dcc", description="Common backdoor port"),
                ReferenceSetEntry(value="6666", source="dcc", description="Common backdoor port"),
                ReferenceSetEntry(value="31337", source="dcc", description="Elite/backdoor port"),
                ReferenceSetEntry(value="12345", source="dcc", description="Common backdoor port"),
                ReferenceSetEntry(value="2323", source="dcc", description="Common backdoor port"),
            ],
            tags=["ports", "suspicious", "dcc"],
        ),
        # Reference Set 6: Authorized Admin Users
        QRadarReferenceSetDefinition(
            set_id="dcc-authorized-admins",
            name="DCC: Authorized Administrative Users",
            set_type=ReferenceSetType.ALNUM,
            data_type=ReferenceSetDataType.STRING,
            description="List of authorized administrative user accounts for data center systems.",
            entries=[
                ReferenceSetEntry(value="admin.dc", source="dcc", description="Data center administrator"),
                ReferenceSetEntry(value="admin.network", source="dcc", description="Network administrator"),
                ReferenceSetEntry(value="admin.security", source="dcc", description="Security administrator"),
                ReferenceSetEntry(value="admin.storage", source="dcc", description="Storage administrator"),
                ReferenceSetEntry(value="admin.database", source="dcc", description="Database administrator"),
            ],
            tags=["users", "admin", "authorized", "dcc"],
        ),
    ]


# ---------------------------------------------------------------------------
# Reference set management
# ---------------------------------------------------------------------------

class QRadarReferenceSetManager:
    """Manages QRadar reference set definitions and deployment."""

    def __init__(self) -> None:
        self._sets: dict[str, QRadarReferenceSetDefinition] = {}

    def add_set(self, ref_set: QRadarReferenceSetDefinition) -> None:
        """Add a reference set definition."""
        self._sets[ref_set.set_id] = ref_set

    def remove_set(self, set_id: str) -> bool:
        """Remove a reference set definition. Returns True if it existed."""
        return self._sets.pop(set_id, None) is not None

    def get_set(self, set_id: str) -> QRadarReferenceSetDefinition | None:
        """Get a reference set definition by ID."""
        return self._sets.get(set_id)

    def get_sets(
        self,
        *,
        tag: str | None = None,
        set_type: ReferenceSetType | None = None,
    ) -> list[QRadarReferenceSetDefinition]:
        """Get reference sets, optionally filtered."""
        results: list[QRadarReferenceSetDefinition] = []
        for ref_set in self._sets.values():
            if tag is not None and tag not in ref_set.tags:
                continue
            if set_type is not None and ref_set.set_type != set_type:
                continue
            results.append(ref_set)
        return results

    def export_to_json(self, *, indent: int = 2) -> str:
        """Export all reference sets as JSON."""
        data = [ref_set.to_dict() for ref_set in self._sets.values()]
        return json.dumps(data, indent=indent)

    def export_to_qradar_format(self) -> str:
        """Export all reference sets in QRadar-compatible format."""
        data = [json.loads(ref_set.to_qradar_json()) for ref_set in self._sets.values()]
        return json.dumps(data, indent=2)

    def load_defaults(self) -> None:
        """Load the default data center reference sets."""
        for ref_set in get_data_center_reference_sets():
            self.add_set(ref_set)

    @property
    def set_count(self) -> int:
        return len(self._sets)
