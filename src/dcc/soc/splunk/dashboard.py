"""Splunk dashboard definitions for DCC SOC monitoring.

Provides XML dashboard definitions that can be deployed to Splunk
via the REST API or imported through the Splunk Web UI.

Usage:
    from dcc.soc.splunk import create_soc_dashboard

    dashboard = create_soc_dashboard()
    print(dashboard.to_xml())
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SplunkDashboardPanel:
    """A single panel in a Splunk dashboard.

    Attributes:
        title: Panel display title.
        search: SPL search query for the panel.
        visualization: Visualization type (e.g., "table", "chart", "single").
        time_range: Default time range (e.g., "-24h", "-7d").
        description: Optional panel description.
    """
    title: str
    search: str
    visualization: str = "table"
    time_range: str = "-24h"
    description: str = ""

    def to_xml(self) -> str:
        """Generate XML for this panel."""
        return f"""
    <panel>
      <title>{self.title}</title>
      <search>
        <query>{self.search}</query>
        <earliest>{self.time_range}</earliest>
        <latest>now</latest>
      </search>
      <option name="count">20</option>
      <option name="dataOverlayMode">none</option>
      <option name="drilldown">cell</option>
      <option name="refresh.display">progressbar</option>
      <option name="rowNumbers">false</option>
      <option name="wrap">true</option>
      <table>
        <option name="count">20</option>
        <option name="dataOverlayMode">none</option>
        <option name="drilldown">cell</option>
        <option name="refresh.display">progressbar</option>
        <option name="rowNumbers">false</option>
        <option name="wrap">true</option>
      </table>
    </panel>"""


@dataclass
class SplunkDashboard:
    """A Splunk dashboard definition.

    Attributes:
        title: Dashboard title.
        description: Dashboard description.
        panels: List of dashboard panels.
        time_range: Default dashboard time range.
        refresh_interval: Auto-refresh interval in seconds (0 = no refresh).
    """
    title: str
    description: str
    panels: list[SplunkDashboardPanel] = field(default_factory=list)
    time_range: str = "-24h"
    refresh_interval: int = 300

    def to_xml(self) -> str:
        """Generate the full dashboard XML."""
        panels_xml = "\n".join(p.to_xml() for p in self.panels)
        refresh = (
            f'<option name="refresh.interval">{self.refresh_interval}</option>'
            if self.refresh_interval > 0
            else ""
        )
        return f"""<dashboard>
  <label>{self.title}</label>
  <description>{self.description}</description>
  <search>
    <query>index=dcc_* sourcetype=dcc:json | head 1</query>
    <earliest>{self.time_range}</earliest>
    <latest>now</latest>
  </search>
  {refresh}
  <row>
    <panel>
      <title>Overview</title>
      <html>
        <h3>{self.description}</h3>
        <p>Data Center Commander SOC Monitoring Dashboard</p>
      </html>
    </panel>
  </row>
  <row>
{panels_xml}
  </row>
</dashboard>"""

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dict suitable for Splunk REST API."""
        return {
            "title": self.title,
            "description": self.description,
            "time_range": self.time_range,
            "refresh_interval": self.refresh_interval,
            "panels": [
                {
                    "title": p.title,
                    "search": p.search,
                    "visualization": p.visualization,
                    "time_range": p.time_range,
                    "description": p.description,
                }
                for p in self.panels
            ],
        }


def create_soc_dashboard() -> SplunkDashboard:
    """Create the default DCC SOC monitoring dashboard.

    Returns:
        SplunkDashboard with panels for:
        - Security event overview
        - Authentication activity
        - Authorization failures
        - Alert severity distribution
        - Top offending IPs
        - Audit trail summary
        - System health status
    """
    return SplunkDashboard(
        title="DCC SOC Monitoring",
        description="Data Center Commander Security Operations Center",
        time_range="-24h",
        refresh_interval=300,
        panels=[
            SplunkDashboardPanel(
                title="Security Events by Category",
                search=(
                    'index=dcc_security sourcetype=dcc:json '
                    "| stats count by category "
                    "| sort -count"
                ),
                visualization="chart",
                time_range="-24h",
                description="Distribution of security events by category",
            ),
            SplunkDashboardPanel(
                title="Authentication Activity",
                search=(
                    'index=dcc_security sourcetype=dcc:json category="authentication" '
                    "| timechart span=1h count by action"
                ),
                visualization="chart",
                time_range="-24h",
                description="Login success/failure trends over time",
            ),
            SplunkDashboardPanel(
                title="Authorization Failures",
                search=(
                    'index=dcc_security sourcetype=dcc:json action="api_rejected" '
                    "| stats count by src_ip, actor_ref "
                    "| sort -count "
                    "| head 20"
                ),
                visualization="table",
                time_range="-24h",
                description="Top sources of authorization failures",
            ),
            SplunkDashboardPanel(
                title="Alert Severity Distribution",
                search=(
                    'index=dcc_alerts sourcetype=dcc:json '
                    "| stats count by severity "
                    "| sort -count"
                ),
                visualization="chart",
                time_range="-24h",
                description="Alerts by severity level",
            ),
            SplunkDashboardPanel(
                title="Top Offending IPs",
                search=(
                    'index=dcc_security sourcetype=dcc:json '
                    '(action="login_failure" OR action="api_rejected" OR action="rate_limit_hit") '
                    "| stats count by src_ip "
                    "| sort -count "
                    "| head 10"
                ),
                visualization="table",
                time_range="-24h",
                description="IP addresses with most security events",
            ),
            SplunkDashboardPanel(
                title="Audit Trail Summary",
                search=(
                    'index=dcc_audit sourcetype=dcc:json '
                    "| stats count by action, success "
                    "| sort -count"
                ),
                visualization="table",
                time_range="-24h",
                description="Audit event summary by action type",
            ),
            SplunkDashboardPanel(
                title="System Health Status",
                search=(
                    'index=dcc_metrics sourcetype=dcc:json metric="health_check" '
                    "| stats latest(status) by host "
                    "| eval health=if(status='healthy', 'OK', 'DEGRADED')"
                ),
                visualization="table",
                time_range="-1h",
                description="Current health status of all monitored hosts",
            ),
            SplunkDashboardPanel(
                title="Tenant Activity",
                search=(
                    'index=dcc_security sourcetype=dcc:json '
                    "| stats count by tenant_id "
                    "| sort -count "
                    "| head 10"
                ),
                visualization="chart",
                time_range="-24h",
                description="Security events by tenant",
            ),
        ],
    )
