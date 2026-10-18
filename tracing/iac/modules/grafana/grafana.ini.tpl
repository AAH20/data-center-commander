[auth.anonymous]
enabled = ${anonymous_enabled}
org_role = ${anonymous_org_role}

[auth]
disable_login_form = ${anonymous_enabled}

[server]
http_port = 3000

[dashboards]
default_home_dashboard_path = /var/lib/grafana/dashboards/tracing.json
