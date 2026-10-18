"""Offense correlation engine for QRadar SOC integration.

Provides correlation between data center events and QRadar offenses,
enabling automated threat detection, root cause analysis, and
incident enrichment. The correlation engine matches events to offenses
based on multiple criteria including IP addresses, ports, protocols,
temporal proximity, and behavioral patterns.

Contract/design only — no live QRadar integration is certified.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .models import (
    OffenseSeverity,
    QRadarEvent,
    QRadarFlow,
    QRadarOffense,
)


# ---------------------------------------------------------------------------
# Correlation strategies
# ---------------------------------------------------------------------------

class CorrelationStrategy(str, Enum):
    """Strategy for correlating events to offenses."""
    EXACT_MATCH = "exact_match"
    FUZZY_MATCH = "fuzzy_match"
    TEMPORAL_PROXIMITY = "temporal_proximity"
    BEHAVIORAL = "behavioral"
    THREAT_INTEL = "threat_intel"
    ASSET_BASED = "asset_based"
    USER_BASED = "user_based"
    NETWORK_BASED = "network_based"


class CorrelationConfidence(str, Enum):
    """Confidence level of a correlation."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ---------------------------------------------------------------------------
# Correlation result models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CorrelationResult:
    """Result of a correlation analysis."""
    correlation_id: str
    offense_id: str
    event_id: str
    strategy: CorrelationStrategy
    confidence: CorrelationConfidence
    confidence_score: float
    matched_fields: list[str] = field(default_factory=list)
    matched_values: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    recommended_action: str = ""
    created_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "correlation_id": self.correlation_id,
            "offense_id": self.offense_id,
            "event_id": self.event_id,
            "strategy": self.strategy.value,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "matched_fields": list(self.matched_fields),
            "matched_values": dict(self.matched_values),
            "explanation": self.explanation,
            "recommended_action": self.recommended_action,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CorrelationResult:
        """Reconstruct from dictionary."""
        return cls(
            correlation_id=str(data["correlation_id"]),
            offense_id=str(data["offense_id"]),
            event_id=str(data["event_id"]),
            strategy=CorrelationStrategy(data.get("strategy", "exact_match")),
            confidence=CorrelationConfidence(data.get("confidence", "low")),
            confidence_score=float(data.get("confidence_score", 0.0)),
            matched_fields=list(data.get("matched_fields", [])),
            matched_values=dict(data.get("matched_values", {})),
            explanation=str(data.get("explanation", "")),
            recommended_action=str(data.get("recommended_action", "")),
            created_at=str(data.get("created_at", dt.datetime.now(dt.timezone.utc).isoformat())),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(slots=True)
class CorrelationReport:
    """Aggregated correlation report."""
    report_id: str
    offense_id: str
    total_events_analyzed: int
    total_correlations_found: int
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    correlations: list[CorrelationResult] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "report_id": self.report_id,
            "offense_id": self.offense_id,
            "total_events_analyzed": self.total_events_analyzed,
            "total_correlations_found": self.total_correlations_found,
            "high_confidence_count": self.high_confidence_count,
            "medium_confidence_count": self.medium_confidence_count,
            "low_confidence_count": self.low_confidence_count,
            "correlations": [c.to_dict() for c in self.correlations],
            "summary": self.summary,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CorrelationReport:
        """Reconstruct from dictionary."""
        return cls(
            report_id=str(data["report_id"]),
            offense_id=str(data["offense_id"]),
            total_events_analyzed=int(data.get("total_events_analyzed", 0)),
            total_correlations_found=int(data.get("total_correlations_found", 0)),
            high_confidence_count=int(data.get("high_confidence_count", 0)),
            medium_confidence_count=int(data.get("medium_confidence_count", 0)),
            low_confidence_count=int(data.get("low_confidence_count", 0)),
            correlations=[CorrelationResult.from_dict(c) for c in data.get("correlations", [])],
            summary=str(data.get("summary", "")),
            created_at=str(data.get("created_at", dt.datetime.now(dt.timezone.utc).isoformat())),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Correlation engine
# ---------------------------------------------------------------------------

class OffenseCorrelationEngine:
    """Engine for correlating data center events with QRadar offenses.

    Supports multiple correlation strategies and provides configurable
    thresholds for confidence scoring.
    """

    def __init__(
        self,
        *,
        high_confidence_threshold: float = 0.8,
        medium_confidence_threshold: float = 0.5,
        low_confidence_threshold: float = 0.2,
        temporal_window_minutes: int = 30,
    ) -> None:
        self.high_threshold = high_confidence_threshold
        self.medium_threshold = medium_confidence_threshold
        self.low_threshold = low_confidence_threshold
        self.temporal_window = dt.timedelta(minutes=temporal_window_minutes)
        self._strategies: dict[CorrelationStrategy, Callable[..., CorrelationResult | None]] = {
            CorrelationStrategy.EXACT_MATCH: self._exact_match,
            CorrelationStrategy.FUZZY_MATCH: self._fuzzy_match,
            CorrelationStrategy.TEMPORAL_PROXIMITY: self._temporal_proximity,
            CorrelationStrategy.BEHAVIORAL: self._behavioral_correlation,
            CorrelationStrategy.THREAT_INTEL: self._threat_intel_correlation,
            CorrelationStrategy.ASSET_BASED: self._asset_based_correlation,
            CorrelationStrategy.USER_BASED: self._user_based_correlation,
            CorrelationStrategy.NETWORK_BASED: self._network_based_correlation,
        }

    def correlate(
        self,
        offense: QRadarOffense,
        events: list[QRadarEvent],
        flows: list[QRadarFlow] | None = None,
    ) -> CorrelationReport:
        """Correlate events with an offense.

        Args:
            offense: The QRadar offense to correlate against.
            events: List of events to analyze.
            flows: Optional list of network flows to include in analysis.

        Returns:
            CorrelationReport with all findings.
        """
        all_results: list[CorrelationResult] = []

        for event in events:
            for strategy, strategy_fn in self._strategies.items():
                result = strategy_fn(offense, event, flows)
                if result is not None:
                    all_results.append(result)

        # Deduplicate by event_id, keeping highest confidence
        deduplicated: dict[str, CorrelationResult] = {}
        for result in all_results:
            existing = deduplicated.get(result.event_id)
            if existing is None or result.confidence_score > existing.confidence_score:
                deduplicated[result.event_id] = result

        final_results = sorted(deduplicated.values(), key=lambda r: r.confidence_score, reverse=True)

        high_count = sum(1 for r in final_results if r.confidence == CorrelationConfidence.HIGH)
        medium_count = sum(1 for r in final_results if r.confidence == CorrelationConfidence.MEDIUM)
        low_count = sum(1 for r in final_results if r.confidence == CorrelationConfidence.LOW)

        summary = self._generate_summary(offense, final_results, high_count, medium_count, low_count)

        return CorrelationReport(
            report_id=f"report-{offense.offense_id}",
            offense_id=offense.offense_id,
            total_events_analyzed=len(events),
            total_correlations_found=len(final_results),
            high_confidence_count=high_count,
            medium_confidence_count=medium_count,
            low_confidence_count=low_count,
            correlations=final_results,
            summary=summary,
            metadata={
                "strategies_used": [s.value for s in self._strategies],
                "temporal_window_minutes": self.temporal_window.total_seconds() / 60,
            },
        )

    def _classify_confidence(self, score: float) -> CorrelationConfidence:
        """Classify a confidence score into a confidence level."""
        if score >= self.high_threshold:
            return CorrelationConfidence.HIGH
        if score >= self.medium_threshold:
            return CorrelationConfidence.MEDIUM
        if score >= self.low_threshold:
            return CorrelationConfidence.LOW
        return CorrelationConfidence.INFO

    def _exact_match(
        self,
        offense: QRadarOffense,
        event: QRadarEvent,
        flows: list[QRadarFlow] | None,
    ) -> CorrelationResult | None:
        """Exact match correlation strategy."""
        matched_fields: list[str] = []
        matched_values: dict[str, Any] = {}
        score = 0.0

        if offense.source_ip and event.source_ip and offense.source_ip == event.source_ip:
            matched_fields.append("source_ip")
            matched_values["source_ip"] = event.source_ip
            score += 0.25

        if offense.destination_ip and event.destination_ip and offense.destination_ip == event.destination_ip:
            matched_fields.append("destination_ip")
            matched_values["destination_ip"] = event.destination_ip
            score += 0.25

        if offense.source_port and event.source_port and offense.source_port == event.source_port:
            matched_fields.append("source_port")
            matched_values["source_port"] = event.source_port
            score += 0.15

        if offense.destination_port and event.destination_port and offense.destination_port == event.destination_port:
            matched_fields.append("destination_port")
            matched_values["destination_port"] = event.destination_port
            score += 0.15

        if offense.protocol and event.protocol and offense.protocol.lower() == event.protocol.lower():
            matched_fields.append("protocol")
            matched_values["protocol"] = event.protocol
            score += 0.1

        if offense.username and event.username and offense.username == event.username:
            matched_fields.append("username")
            matched_values["username"] = event.username
            score += 0.1

        if not matched_fields:
            return None

        confidence = self._classify_confidence(score)
        return CorrelationResult(
            correlation_id=f"exact-{offense.offense_id}-{event.event_id}",
            offense_id=offense.offense_id,
            event_id=event.event_id,
            strategy=CorrelationStrategy.EXACT_MATCH,
            confidence=confidence,
            confidence_score=round(score, 2),
            matched_fields=matched_fields,
            matched_values=matched_values,
            explanation=f"Exact match on {', '.join(matched_fields)}",
            recommended_action=self._recommend_action(confidence, matched_fields),
        )

    def _fuzzy_match(
        self,
        offense: QRadarOffense,
        event: QRadarEvent,
        flows: list[QRadarFlow] | None,
    ) -> CorrelationResult | None:
        """Fuzzy match correlation strategy using partial matching."""
        matched_fields: list[str] = []
        matched_values: dict[str, Any] = {}
        score = 0.0

        # Subnet matching for IPs
        if offense.source_ip and event.source_ip:
            if self._same_subnet(offense.source_ip, event.source_ip):
                matched_fields.append("source_subnet")
                matched_values["source_subnet"] = event.source_ip
                score += 0.15

        if offense.destination_ip and event.destination_ip:
            if self._same_subnet(offense.destination_ip, event.destination_ip):
                matched_fields.append("destination_subnet")
                matched_values["destination_subnet"] = event.destination_ip
                score += 0.15

        # Port range matching
        if offense.destination_port and event.destination_port:
            if abs(offense.destination_port - event.destination_port) <= 10:
                matched_fields.append("destination_port_range")
                matched_values["destination_port_range"] = event.destination_port
                score += 0.1

        # Protocol family matching
        if offense.protocol and event.protocol:
            if self._same_protocol_family(offense.protocol, event.protocol):
                matched_fields.append("protocol_family")
                matched_values["protocol_family"] = event.protocol
                score += 0.1

        if not matched_fields:
            return None

        confidence = self._classify_confidence(score)
        return CorrelationResult(
            correlation_id=f"fuzzy-{offense.offense_id}-{event.event_id}",
            offense_id=offense.offense_id,
            event_id=event.event_id,
            strategy=CorrelationStrategy.FUZZY_MATCH,
            confidence=confidence,
            confidence_score=round(score, 2),
            matched_fields=matched_fields,
            matched_values=matched_values,
            explanation=f"Fuzzy match on {', '.join(matched_fields)}",
            recommended_action=self._recommend_action(confidence, matched_fields),
        )

    def _temporal_proximity(
        self,
        offense: QRadarOffense,
        event: QRadarEvent,
        flows: list[QRadarFlow] | None,
    ) -> CorrelationResult | None:
        """Temporal proximity correlation strategy."""
        if not offense.created_at or not event.event_time:
            return None

        try:
            offense_time = dt.datetime.fromisoformat(offense.created_at.replace("Z", "+00:00"))
            event_time = dt.datetime.fromisoformat(event.event_time.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

        time_diff = abs((event_time - offense_time).total_seconds())
        window_seconds = self.temporal_window.total_seconds()

        if time_diff > window_seconds:
            return None

        # Score based on proximity (closer = higher score)
        score = 1.0 - (time_diff / window_seconds)
        score = max(0.1, min(1.0, score))

        confidence = self._classify_confidence(score)
        return CorrelationResult(
            correlation_id=f"temporal-{offense.offense_id}-{event.event_id}",
            offense_id=offense.offense_id,
            event_id=event.event_id,
            strategy=CorrelationStrategy.TEMPORAL_PROXIMITY,
            confidence=confidence,
            confidence_score=round(score, 2),
            matched_fields=["time"],
            matched_values={
                "offense_time": offense.created_at,
                "event_time": event.event_time,
                "time_diff_seconds": time_diff,
            },
            explanation=f"Event occurred {time_diff:.0f}s from offense creation",
            recommended_action="Review temporal relationship" if confidence in (CorrelationConfidence.HIGH, CorrelationConfidence.MEDIUM) else "",
        )

    def _behavioral_correlation(
        self,
        offense: QRadarOffense,
        event: QRadarEvent,
        flows: list[QRadarFlow] | None,
    ) -> CorrelationResult | None:
        """Behavioral correlation strategy."""
        matched_fields: list[str] = []
        matched_values: dict[str, Any] = {}
        score = 0.0

        # Check for similar event categories
        if event.category.value in offense.categories:
            matched_fields.append("category")
            matched_values["category"] = event.category.value
            score += 0.3

        # Check for similar severity patterns
        event_severity = event.severity
        if offense.severity == OffenseSeverity.CRITICAL and event_severity >= 8:
            matched_fields.append("severity_pattern")
            matched_values["severity_pattern"] = "high"
            score += 0.2
        elif offense.severity == OffenseSeverity.HIGH and event_severity >= 6:
            matched_fields.append("severity_pattern")
            matched_values["severity_pattern"] = "elevated"
            score += 0.15

        # Check for similar credibility/relevance patterns
        if event.credibility >= 7 and offense.credibility >= 7:
            matched_fields.append("credibility")
            matched_values["credibility"] = event.credibility
            score += 0.1

        if not matched_fields:
            return None

        confidence = self._classify_confidence(score)
        return CorrelationResult(
            correlation_id=f"behavioral-{offense.offense_id}-{event.event_id}",
            offense_id=offense.offense_id,
            event_id=event.event_id,
            strategy=CorrelationStrategy.BEHAVIORAL,
            confidence=confidence,
            confidence_score=round(score, 2),
            matched_fields=matched_fields,
            matched_values=matched_values,
            explanation=f"Behavioral match on {', '.join(matched_fields)}",
            recommended_action=self._recommend_action(confidence, matched_fields),
        )

    def _threat_intel_correlation(
        self,
        offense: QRadarOffense,
        event: QRadarEvent,
        flows: list[QRadarFlow] | None,
    ) -> CorrelationResult | None:
        """Threat intelligence correlation strategy."""
        matched_fields: list[str] = []
        matched_values: dict[str, Any] = {}
        score = 0.0

        # Check for threat intel indicators in event metadata
        event_threat_intel = event.custom_properties.get("threat_intel_match", False)
        if event_threat_intel:
            matched_fields.append("threat_intel")
            matched_values["threat_intel"] = True
            score += 0.4

        # Check for known bad IPs
        dest_country = event.destination_country
        if dest_country and dest_country in ("CN", "RU", "KP", "IR"):
            matched_fields.append("destination_country_risk")
            matched_values["destination_country_risk"] = dest_country
            score += 0.2

        # Check for suspicious ports
        if event.destination_port and event.destination_port in (4444, 5555, 6666, 31337, 12345):
            matched_fields.append("suspicious_port")
            matched_values["suspicious_port"] = event.destination_port
            score += 0.2

        if not matched_fields:
            return None

        confidence = self._classify_confidence(score)
        return CorrelationResult(
            correlation_id=f"threatintel-{offense.offense_id}-{event.event_id}",
            offense_id=offense.offense_id,
            event_id=event.event_id,
            strategy=CorrelationStrategy.THREAT_INTEL,
            confidence=confidence,
            confidence_score=round(score, 2),
            matched_fields=matched_fields,
            matched_values=matched_values,
            explanation=f"Threat intel match on {', '.join(matched_fields)}",
            recommended_action="Escalate to threat intel team" if confidence == CorrelationConfidence.HIGH else "",
        )

    def _asset_based_correlation(
        self,
        offense: QRadarOffense,
        event: QRadarEvent,
        flows: list[QRadarFlow] | None,
    ) -> CorrelationResult | None:
        """Asset-based correlation strategy."""
        matched_fields: list[str] = []
        matched_values: dict[str, Any] = {}
        score = 0.0

        if offense.source_asset_id and event.source_asset_id and offense.source_asset_id == event.source_asset_id:
            matched_fields.append("source_asset")
            matched_values["source_asset"] = event.source_asset_id
            score += 0.35

        if offense.destination_asset_id and event.destination_asset_id and offense.destination_asset_id == event.destination_asset_id:
            matched_fields.append("destination_asset")
            matched_values["destination_asset"] = event.destination_asset_id
            score += 0.35

        if not matched_fields:
            return None

        confidence = self._classify_confidence(score)
        return CorrelationResult(
            correlation_id=f"asset-{offense.offense_id}-{event.event_id}",
            offense_id=offense.offense_id,
            event_id=event.event_id,
            strategy=CorrelationStrategy.ASSET_BASED,
            confidence=confidence,
            confidence_score=round(score, 2),
            matched_fields=matched_fields,
            matched_values=matched_values,
            explanation=f"Asset match on {', '.join(matched_fields)}",
            recommended_action=self._recommend_action(confidence, matched_fields),
        )

    def _user_based_correlation(
        self,
        offense: QRadarOffense,
        event: QRadarEvent,
        flows: list[QRadarFlow] | None,
    ) -> CorrelationResult | None:
        """User-based correlation strategy."""
        if not offense.username or not event.username:
            return None

        if offense.username != event.username:
            return None

        score = 0.5
        confidence = self._classify_confidence(score)

        return CorrelationResult(
            correlation_id=f"user-{offense.offense_id}-{event.event_id}",
            offense_id=offense.offense_id,
            event_id=event.event_id,
            strategy=CorrelationStrategy.USER_BASED,
            confidence=confidence,
            confidence_score=round(score, 2),
            matched_fields=["username"],
            matched_values={"username": event.username},
            explanation=f"User match: {event.username}",
            recommended_action="Review user activity" if confidence in (CorrelationConfidence.HIGH, CorrelationConfidence.MEDIUM) else "",
        )

    def _network_based_correlation(
        self,
        offense: QRadarOffense,
        event: QRadarEvent,
        flows: list[QRadarFlow] | None,
    ) -> CorrelationResult | None:
        """Network-based correlation strategy using flow data."""
        if not flows:
            return None

        matched_fields: list[str] = []
        matched_values: dict[str, Any] = {}
        score = 0.0

        for flow in flows:
            if offense.source_ip and flow.source_ip == offense.source_ip:
                matched_fields.append("flow_source_ip")
                matched_values["flow_source_ip"] = flow.source_ip
                score += 0.2

            if offense.destination_ip and flow.destination_ip == offense.destination_ip:
                matched_fields.append("flow_destination_ip")
                matched_values["flow_destination_ip"] = flow.destination_ip
                score += 0.2

            if offense.destination_port and flow.destination_port == offense.destination_port:
                matched_fields.append("flow_destination_port")
                matched_values["flow_destination_port"] = flow.destination_port
                score += 0.15

        if not matched_fields:
            return None

        confidence = self._classify_confidence(score)
        return CorrelationResult(
            correlation_id=f"network-{offense.offense_id}-{event.event_id}",
            offense_id=offense.offense_id,
            event_id=event.event_id,
            strategy=CorrelationStrategy.NETWORK_BASED,
            confidence=confidence,
            confidence_score=round(score, 2),
            matched_fields=matched_fields,
            matched_values=matched_values,
            explanation=f"Network flow match on {', '.join(matched_fields)}",
            recommended_action=self._recommend_action(confidence, matched_fields),
        )

    # -- Helper methods -----------------------------------------------------

    def _same_subnet(self, ip1: str, ip2: str, prefix: int = 24) -> bool:
        """Check if two IPs are in the same subnet."""
        try:
            parts1 = ip1.split(".")[:3]
            parts2 = ip2.split(".")[:3]
            return parts1 == parts2
        except (IndexError, AttributeError):
            return False

    def _same_protocol_family(self, proto1: str, proto2: str) -> bool:
        """Check if two protocols belong to the same family."""
        family_map = {
            "tcp": ["tcp", "http", "https", "ssh", "ftp", "smtp"],
            "udp": ["udp", "dns", "dhcp", "snmp", "ntp"],
            "icmp": ["icmp", "icmpv6"],
        }
        for family, protocols in family_map.items():
            if proto1.lower() in protocols and proto2.lower() in protocols:
                return True
        return False

    def _recommend_action(self, confidence: CorrelationConfidence, matched_fields: list[str]) -> str:
        """Generate a recommended action based on confidence and matched fields."""
        if confidence == CorrelationConfidence.HIGH:
            if "source_ip" in matched_fields or "destination_ip" in matched_fields:
                return "Block investigated IP and escalate to SOC L3"
            if "username" in matched_fields:
                return "Disable user account and investigate"
            return "Escalate to SOC L3 for immediate investigation"
        if confidence == CorrelationConfidence.MEDIUM:
            return "Review and monitor closely"
        if confidence == CorrelationConfidence.LOW:
            return "Log for future reference"
        return ""

    def _generate_summary(
        self,
        offense: QRadarOffense,
        results: list[CorrelationResult],
        high_count: int,
        medium_count: int,
        low_count: int,
    ) -> str:
        """Generate a human-readable summary of the correlation analysis."""
        if not results:
            return f"No correlations found for offense {offense.offense_id}."

        parts = [
            f"Correlation analysis for offense {offense.offense_id} ({offense.severity.value} severity):",
            f"- {len(results)} total correlations found",
            f"- {high_count} high confidence",
            f"- {medium_count} medium confidence",
            f"- {low_count} low confidence",
        ]

        if high_count > 0:
            top = results[0]
            parts.append(f"- Top correlation: {top.explanation} (score: {top.confidence_score})")

        return "\n".join(parts)
