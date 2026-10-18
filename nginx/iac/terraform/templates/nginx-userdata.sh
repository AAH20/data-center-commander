#!/bin/bash
# =============================================================================
# Data Center Commander — Nginx UserData Script
# =============================================================================
# Installs and configures Nginx as a reverse proxy / load balancer
# for DCC API instances. This script runs on EC2 launch.
# =============================================================================

set -euo pipefail

exec > >(tee /var/log/user-data.log) 2>&1

echo "=== DCC Nginx UserData — starting at $(date) ==="

# Update system
dnf update -y

# Install Nginx
dnf install -y nginx

# Install certbot for Let's Encrypt (optional)
dnf install -y certbot python3-certbot-nginx || true

# Create Nginx configuration directory
mkdir -p /etc/nginx/conf.d
mkdir -p /etc/nginx/certs

# Generate self-signed cert for initial setup (replace with ACM/Let's Encrypt in production)
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout /etc/nginx/certs/dcc.key \
  -out /etc/nginx/certs/dcc.crt \
  -subj "/C=US/ST=State/L=City/O=DataCenterCommander/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null || true

# Write the main Nginx configuration
cat > /etc/nginx/nginx.conf <<'NGINX_CONF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml application/xml+rss text/javascript
               image/svg+xml;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=health_limit:10m rate=1r/s;

    # Upstream: DCC API backends
    upstream dcc_api {
        least_conn;
        server 127.0.0.1:8790 weight=5 max_fails=3 fail_timeout=30s;
        server 127.0.0.1:8791 weight=5 max_fails=3 fail_timeout=30s;
        server 127.0.0.1:8792 weight=5 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    # Upstream: Health check
    upstream dcc_health {
        server 127.0.0.1:8790;
        server 127.0.0.1:8791;
        server 127.0.0.1:8792;
    }

    # WebSocket upgrade map
    map $http_upgrade $connection_upgrade {
        default upgrade;
        ''      close;
    }

    # HTTP → HTTPS redirect
    server {
        listen 80;
        server_name _;

        location /healthz {
            proxy_pass http://dcc_health;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 5s;
            proxy_read_timeout 10s;
        }

        location /readyz {
            proxy_pass http://dcc_health;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 5s;
            proxy_read_timeout 10s;
        }

        location / {
            return 301 https://$host$request_uri;
        }
    }

    # HTTPS (primary)
    server {
        listen 443 ssl;
        http2 on;
        server_name _;

        # TLS
        ssl_certificate /etc/nginx/certs/dcc.crt;
        ssl_certificate_key /etc/nginx/certs/dcc.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        # Security headers
        add_header X-Frame-Options DENY always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "no-referrer" always;
        add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';" always;
        add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

        # Health endpoints (no rate limit)
        location /healthz {
            proxy_pass http://dcc_health;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 5s;
            proxy_read_timeout 10s;
        }

        location /readyz {
            proxy_pass http://dcc_health;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 5s;
            proxy_read_timeout 10s;
        }

        # API endpoints (rate limited)
        location /v1/ {
            limit_req zone=api_limit burst=20 nodelay;

            proxy_pass http://dcc_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Request-ID $request_id;

            proxy_connect_timeout 10s;
            proxy_send_timeout 120s;
            proxy_read_timeout 120s;

            proxy_buffering on;
            proxy_buffer_size 16k;
            proxy_buffers 4 32k;
            proxy_busy_buffers_size 64k;
        }

        # Static UI assets
        location /assets/ {
            limit_req zone=api_limit burst=30 nodelay;

            proxy_pass http://dcc_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_cache_valid 200 1h;
            proxy_cache_valid 404 1m;
            expires 1h;
        }

        # Root / UI
        location / {
            limit_req zone=api_limit burst=20 nodelay;

            proxy_pass http://dcc_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Request-ID $request_id;

            proxy_connect_timeout 10s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }

        # Deny hidden files
        location ~ /\. {
            deny all;
            access_log off;
            log_not_found off;
        }
    }
}
NGINX_CONF

# Test and start Nginx
nginx -t
systemctl enable nginx
systemctl start nginx

# Install and configure CloudWatch agent
dnf install -y amazon-cloudwatch-agent || true

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'CW_AGENT'
{
  "metrics": {
    "namespace": "DCC/Nginx",
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
      },
      "netstat": {
        "measurement": ["tcp_established", "tcp_time_wait"],
        "metrics_collection_interval": 60
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/nginx/access.log",
            "log_group_name": "/dcc/nginx/access",
            "log_stream_name": "{instance_id}"
          },
          {
            "file_path": "/var/log/nginx/error.log",
            "log_group_name": "/dcc/nginx/error",
            "log_stream_name": "{instance_id}"
          }
        ]
      }
    }
  }
}
CW_AGENT

/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json || true

echo "=== DCC Nginx UserData — completed at $(date) ==="
