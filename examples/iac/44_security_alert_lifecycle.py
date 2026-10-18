"""Example: Security alert lifecycle management.

Demonstrates acknowledging, resolving, and dismissing alerts.
"""
from dcc.iac_observability.security_alerts import SecurityAlert, SecurityFinding, SecurityAlertType, SecurityAlertSeverity

finding = SecurityFinding(
    alert_type=SecurityAlertType.OPEN_PORT,
    severity=SecurityAlertSeverity.HIGH,
    resource_id="i-123",
    resource_name="web-1",
    resource_type="aws_instance",
    description="Port 22 open to world",
    remediation="Restrict to specific IPs",
)

alert = SecurityAlert(finding=finding)
print(f"Alert ID: {alert.alert_id}")
print(f"Status: {alert.status}")

alert.acknowledge("admin")
print(f"After acknowledge - status: {alert.status}, by: {alert.acknowledged_by}")

alert.resolve()
print(f"After resolve - status: {alert.status}")
