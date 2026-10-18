#!/bin/bash
# =============================================================================
# Data Center Commander — Traefik UserData Script
# =============================================================================
# Installs and configures Traefik as a reverse proxy / load balancer
# for DCC API instances. This script runs on EC2 launch.
# =============================================================================

set -euo pipefail

exec > >(tee /var/log/user-data.log) 2>&1

echo "=== DCC Traefik UserData — starting at $(date) ==="

# Update system
dnf update -y

# Install Traefik
TRAEFIK_VERSION="v3.1.0"
curl -fsSL "https://github.com/traefik/traefik/releases/download/${TRAEFIK_VERSION}/traefik_${TRAEFIK_VERSION}_linux_amd64.tar.gz" \
  -o /tmp/traefik.tar.gz
tar -xzf /tmp/traefik.tar.gz -C /usr/local/bin/
chmod +x /usr/local/bin/traefik
rm /tmp/traefik.tar.gz

# Create Traefik user
useradd --system --shell /bin/false traefik || true

# Create directories
mkdir -p /etc/traefik/certs
mkdir -p /var/log/traefik

# Generate self-signed cert for initial setup
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout /etc/traefik/certs/dcc.key \
  -out /etc/traefik/certs/dcc.crt \
  -subj "/C=US/ST=State/L=City/O=DataCenterCommander/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null || true

# Traefik static configuration
cat > /etc/traefik/traefik.yml <<'TRAEFIK_STATIC'
global:
  checkNewVersion: false
  sendAnonymousUsage: false

api:
  dashboard: true
  insecure: false

ping:
  entryPoint: "traefik"

log:
  level: INFO
  format: json
  filePath: "/var/log/traefik/traefik.log"

accessLog:
  format: json
  filePath: "/var/log/traefik/access.log"

entryPoints:
  web:
    address: ":80"
    transport:
      respondingTimeouts:
        readTimeout: 10s
        writeTimeout: 10s
        idleTimeout: 30s
    forwardedHeaders:
      insecure: true
    proxyProtocol:
      insecure: true

  websecure:
    address: ":443"
    transport:
      respondingTimeouts:
        readTimeout: 10s
        writeTimeout: 120s
        idleTimeout: 30s
    forwardedHeaders:
      insecure: true
    proxyProtocol:
      insecure: true

  traefik:
    address: ":8080"

providers:
  file:
    directory: /etc/traefik/dynamic
    watch: true

certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@example.com
      storage: /etc/traefik/acme.json
      tlsChallenge: {}

serversTransport:
  insecureSkipVerify: true
TRAEFIK_STATIC

# Traefik dynamic configuration
mkdir -p /etc/traefik/dynamic

cat > /etc/traefik/dynamic/dcc.yml <<'TRAEFIK_DYNAMIC'
http:
  routers:
    # Health check router (no TLS, no rate limit)
    dcc-health:
      rule: "PathPrefix(`/healthz`) || PathPrefix(`/readyz`)"
      service: dcc-health
      entryPoints:
        - web
      middlewares:
        - dcc-headers

    # API router (rate limited)
    dcc-api:
      rule: "PathPrefix(`/v1/`)"
      service: dcc-api
      entryPoints:
        - web
      middlewares:
        - dcc-ratelimit
        - dcc-headers

    # Static assets router
    dcc-assets:
      rule: "PathPrefix(`/assets/`)"
      service: dcc-api
      entryPoints:
        - web
      middlewares:
        - dcc-ratelimit-assets
        - dcc-headers
        - dcc-cache

    # Main UI router
    dcc-ui:
      rule: "PathPrefix(`/`)"
      service: dcc-api
      entryPoints:
        - web
      middlewares:
        - dcc-ratelimit
        - dcc-headers

    # HTTPS routers
    dcc-health-secure:
      rule: "PathPrefix(`/healthz`) || PathPrefix(`/readyz`)"
      service: dcc-health
      entryPoints:
        - websecure
      middlewares:
        - dcc-headers
      tls: {}

    dcc-api-secure:
      rule: "PathPrefix(`/v1/`)"
      service: dcc-api
      entryPoints:
        - websecure
      middlewares:
        - dcc-ratelimit
        - dcc-headers
      tls: {}

    dcc-assets-secure:
      rule: "PathPrefix(`/assets/`)"
      service: dcc-api
      entryPoints:
        - websecure
      middlewares:
        - dcc-ratelimit-assets
        - dcc-headers
        - dcc-cache
      tls: {}

    dcc-ui-secure:
      rule: "PathPrefix(`/`)"
      service: dcc-api
      entryPoints:
        - websecure
      middlewares:
        - dcc-ratelimit
        - dcc-headers
      tls: {}

  services:
    dcc-api:
      loadBalancer:
        servers:
          - url: "http://127.0.0.1:8790"
          - url: "http://127.0.0.1:8791"
          - url: "http://127.0.0.1:8792"
        healthCheck:
          path: /healthz
          interval: 10s
          timeout: 5s
        passHostHeader: true
        responseForwarding:
          flushInterval: 100ms

    dcc-health:
      loadBalancer:
        servers:
          - url: "http://127.0.0.1:8790"
          - url: "http://127.0.0.1:8791"
          - url: "http://127.0.0.1:8792"
        healthCheck:
          path: /healthz
          interval: 10s
          timeout: 5s
        passHostHeader: true

  middlewares:
    dcc-ratelimit:
      rateLimit:
        average: 10
        burst: 20
        sourceCriterion:
          ipStrategy:
            depth: 1

    dcc-ratelimit-assets:
      rateLimit:
        average: 10
        burst: 30
        sourceCriterion:
          ipStrategy:
            depth: 1

    dcc-headers:
      headers:
        frameDeny: true
        contentTypeNosniff: true
        browserXssFilter: true
        referrerPolicy: "no-referrer"
        customResponseHeaders:
          X-Request-ID: "%[req.headers.X-Request-ID]"
        contentSecurityPolicy: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';"
        permissionsPolicy: "geolocation=(), microphone=(), camera=()"

    dcc-cache:
      headers:
        customResponseHeaders:
          Cache-Control: "public, max-age=3600"
TRAEFIK_DYNAMIC

# Create systemd service
cat > /etc/systemd/system/traefik.service <<'TRAEFIK_SERVICE'
[Unit]
Description=Traefik Load Balancer
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=traefik
Group=traefik
ExecStart=/usr/local/bin/traefik --configFile=/etc/traefik/traefik.yml
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=traefik

# Security
NoNewPrivileges=true
ProtectHome=true
ProtectSystem=full
ReadWritePaths=/var/log/traefik /etc/traefik/certs /etc/traefik/acme.json

[Install]
WantedBy=multi-user.target
TRAEFIK_SERVICE

# Set permissions
chown -R traefik:traefik /etc/traefik /var/log/traefik
chmod 600 /etc/traefik/certs/dcc.key

# Start Traefik
systemctl daemon-reload
systemctl enable traefik
systemctl start traefik

# Install and configure CloudWatch agent
dnf install -y amazon-cloudwatch-agent || true

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'CW_AGENT'
{
  "metrics": {
    "namespace": "DCC/Traefik",
    "metrics_collected": {
      "cpu": {
        "measurement": ["cpu_usage_idle", "cpu_usage_iowait", "cpu_usage_user", "cpu_usage_system"],
        "metrics_collection_interval": 60,
        "totalcpu": true
      },
      "disk": {
        "measurement": ["used_percent", "inodes_free"],
        "metrics_collection_interval": 60,
        "resources": ["/"]
      },
      "mem": {
        "measurement": ["mem_used_percent"],
        "metrics_collection_interval": 60
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/traefik/traefik.log",
            "log_group_name": "/dcc/traefik/app",
            "log_stream_name": "{instance_id}"
          },
          {
            "file_path": "/var/log/traefik/access.log",
            "log_group_name": "/dcc/traefik/access",
            "log_stream_name": "{instance_id}"
          }
        ]
      }
    }
  }
}
CW_AGENT

/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json || true

echo "=== DCC Traefik UserData — completed at $(date) ==="
