#!/usr/bin/env bash
# Generate self-signed TLS certificate for local nginx testing.
# In production, replace with real certificates (e.g., Let's Encrypt).

set -euo pipefail

CERT_DIR="$(cd "$(dirname "$0")" && pwd)/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/dcc.key" \
  -out "$CERT_DIR/dcc.crt" \
  -subj "/C=US/ST=State/L=City/O=DataCenterCommander/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

echo "Self-signed certificate generated in $CERT_DIR"
echo "  - dcc.crt (certificate)"
echo "  - dcc.key (private key)"
