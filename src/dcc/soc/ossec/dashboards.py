"""OSSEC dashboards — visualization and reporting."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from .models import OSSECAlert, OSSECGroup, OSSECStatus, Severity


class OSSECDashboard:
    """OSSEC SOC dashboard generator."""

    def __init__(self) -> None:
        self.alerts: list[OSSECAlert] = []
        self.agents: list[OSSECStatus] = []

    def load_alerts(self, alerts: list[OSSECAlert]) -> None:
        """Load alerts into the dashboard."""
        self.alerts = alerts

    def load_agents(self, agents: list[OSSECStatus]) -> None:
        """Load agent status into the dashboard."""
        self.agents = agents

    def summary(self) -> dict:
        """Generate dashboard summary."""
        return {
            "total_alerts": len(self.alerts),
            "total_agents": len(self.agents),
            "active_agents": sum(1 for a in self.agents if a.status == "active"),
            "severity_breakdown": self._severity_breakdown(),
            "group_breakdown": self._group_breakdown(),
            "top_rules": self._top_rules(),
            "top_agents": self._top_agents(),
            "recent_alerts": self._recent_alerts(10),
            "mitre_coverage": self._mitre_coverage(),
            "compliance_summary": self._compliance_summary(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _severity_breakdown(self) -> dict[str, int]:
        """Count alerts by severity."""
        counts: Counter[str] = Counter()
        for alert in self.alerts:
            counts[alert.severity.name.lower()] += 1
        return dict(counts)

    def _group_breakdown(self) -> dict[str, int]:
        """Count alerts by rule group."""
        counts: Counter[str] = Counter()
        for alert in self.alerts:
            counts[alert.rule.group.value] += 1
        return dict(counts)

    def _top_rules(self, limit: int = 10) -> list[dict]:
        """Get top triggered rules."""
        counts: Counter[str] = Counter()
        for alert in self.alerts:
            counts[alert.rule.description] += 1

        return [
            {"rule": rule, "count": count}
            for rule, count in counts.most_common(limit)
        ]

    def _top_agents(self, limit: int = 10) -> list[dict]:
        """Get agents with most alerts."""
        counts: Counter[str] = Counter()
        for alert in self.alerts:
            counts[alert.agent_name] += 1

        return [
            {"agent": agent, "count": count}
            for agent, count in counts.most_common(limit)
        ]

    def _recent_alerts(self, limit: int = 10) -> list[dict]:
        """Get most recent alerts."""
        sorted_alerts = sorted(
            self.alerts, key=lambda a: a.timestamp, reverse=True
        )
        return [
            {
                "alert_id": a.alert_id,
                "timestamp": a.timestamp,
                "severity": a.severity.value,
                "description": a.rule.description,
                "agent": a.agent_name,
                "location": a.location,
            }
            for a in sorted_alerts[:limit]
        ]

    def _mitre_coverage(self) -> dict[str, int]:
        """MITRE ATT&CK technique coverage."""
        counts: Counter[str] = Counter()
        for alert in self.alerts:
            if alert.mitre_technique:
                counts[alert.mitre_technique] += 1
        return dict(counts)

    def _compliance_summary(self) -> dict[str, int]:
        """Compliance framework reference counts."""
        counts: Counter[str] = Counter()
        for alert in self.alerts:
            for ref in alert.compliance_refs:
                counts[ref] += 1
        return dict(counts)

    def export_json(self, path: str) -> None:
        """Export dashboard data as JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.summary(), f, indent=2, default=str)

    def export_html(self, path: str) -> None:
        """Export dashboard as HTML report."""
        data = self.summary()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>OSSEC SOC Dashboard</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        .header {{ text-align: center; padding: 20px; background: #16213e; border-radius: 8px; margin-bottom: 20px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .card {{ background: #16213e; padding: 20px; border-radius: 8px; }}
        .card h3 {{ margin-top: 0; color: #e94560; }}
        .metric {{ font-size: 2em; font-weight: bold; color: #e94560; }}
        .severity-critical {{ color: #ff0000; }}
        .severity-high {{ color: #ff6600; }}
        .severity-medium {{ color: #ffcc00; }}
        .severity-low {{ color: #00cc00; }}
        .severity-info {{ color: #0099ff; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ color: #e94560; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>OSSEC SOC Dashboard</h1>
        <p>Generated: {data['generated_at']}</p>
    </div>

    <div class="grid">
        <div class="card">
            <h3>Overview</h3>
            <div class="metric">{data['total_alerts']}</div>
            <p>Total Alerts</p>
            <div class="metric">{data['active_agents']}/{data['total_agents']}</div>
            <p>Active Agents</p>
        </div>

        <div class="card">
            <h3>Severity Breakdown</h3>
            <table>
                <tr><th>Severity</th><th>Count</th></tr>
                {''.join(f'<tr><td class="severity-{s}">{s.title()}</td><td>{c}</td></tr>' for s, c in data['severity_breakdown'].items())}
            </table>
        </div>

        <div class="card">
            <h3>Top Rules</h3>
            <table>
                <tr><th>Rule</th><th>Count</th></tr>
                {''.join(f'<tr><td>{r["rule"]}</td><td>{r["count"]}</td></tr>' for r in data['top_rules'][:5])}
            </table>
        </div>

        <div class="card">
            <h3>Group Breakdown</h3>
            <table>
                <tr><th>Group</th><th>Count</th></tr>
                {''.join(f'<tr><td>{g}</td><td>{c}</td></tr>' for g, c in data['group_breakdown'].items())}
            </table>
        </div>

        <div class="card">
            <h3>MITRE ATT&CK</h3>
            <table>
                <tr><th>Technique</th><th>Count</th></tr>
                {''.join(f'<tr><td>{t}</td><td>{c}</td></tr>' for t, c in data['mitre_coverage'].items())}
            </table>
        </div>

        <div class="card">
            <h3>Compliance</h3>
            <table>
                <tr><th>Framework</th><th>Count</th></tr>
                {''.join(f'<tr><td>{r}</td><td>{c}</td></tr>' for r, c in data['compliance_summary'].items())}
            </table>
        </div>
    </div>

    <div class="card" style="margin-top: 20px;">
        <h3>Recent Alerts</h3>
        <table>
            <tr><th>Time</th><th>Severity</th><th>Description</th><th>Agent</th></tr>
            {''.join(f'<tr><td>{a["timestamp"]}</td><td class="severity-{a["severity"]}">{a["severity"].title()}</td><td>{a["description"]}</td><td>{a["agent"]}</td></tr>' for a in data['recent_alerts'])}
        </table>
    </div>
</body>
</html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
