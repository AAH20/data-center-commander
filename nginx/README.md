# Nginx Load Balancer

TLS-terminating reverse proxy and load balancer for the Data Center Commander API.

## Architecture

```
Client ──► Nginx (443/80) ──► DCC API instances (8790, 8791, 8792)
                              (loopback-only, unauthenticated)
```

- **Nginx** handles TLS termination, rate limiting, security headers, and
  load balancing across multiple backend instances using `least_conn`.
- **DCC API** instances run `scripts/run-local.py` and remain loopback-only.
  They are never exposed directly.

## Files

| File | Purpose |
|---|---|
| `nginx.conf` | Main nginx configuration (TLS, rate limiting, upstream, security headers) |
| `docker-compose.yml` | Full stack: nginx + 3 DCC API instances |
| `Dockerfile` | Minimal Python image for DCC API containers |
| `generate-certs.sh` | Self-signed cert generator for local testing |

## Quick Start

```bash
cd nginx/

# 1. Generate self-signed TLS certificates
./generate-certs.sh

# 2. Set your database URL (or use the default in docker-compose.yml)
export DCC_DATABASE_URL='postgresql://127.0.0.1/data_center_commander_dev'

# 3. Start the stack
docker compose up -d

# 4. Open the UI
# https://localhost/
# (Accept the self-signed cert warning)
```

## Configuration

### Adding/removing backends

Edit the `upstream dcc_api` block in `nginx.conf`:

```nginx
upstream dcc_api {
    least_conn;
    server 127.0.0.1:8790 weight=5;
    server 127.0.0.1:8791 weight=5;
    # add more...
}
```

### Rate limiting

Adjust in `nginx.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
# and in location blocks:
limit_req zone=api_limit burst=20 nodelay;
```

### TLS certificates

Replace the self-signed certs in `certs/` with real certificates:

```bash
# Let's Encrypt example (requires certbot)
certbot certonly --standalone -d your-domain.com
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem certs/dcc.crt
cp /etc/letsencrypt/live/your-domain.com/privkey.pem certs/dcc.key
```

## Security Notes

- The DCC API is **unauthenticated and loopback-only** — nginx is the only
  exposed entry point.
- All security headers (CSP, X-Frame-Options, etc.) are set by nginx.
- Rate limiting is applied to all API and UI endpoints.
- Health endpoints (`/healthz`, `/readyz`) are not rate-limited for LB probes.
- The API's same-origin POST policy still applies at the application layer.
