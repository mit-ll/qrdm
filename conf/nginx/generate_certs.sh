#!/usr/bin/env bash
# Generate self-signed SSL/TLS certificate and private key for QRDM Nginx
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRIVATE_DIR="${SCRIPT_DIR}/private"

mkdir -p "${PRIVATE_DIR}"

KEY_FILE="${PRIVATE_DIR}/server-key.pem"
CERT_FILE="${PRIVATE_DIR}/server-cert.pem"

if [ -f "${KEY_FILE}" ] && [ -f "${CERT_FILE}" ]; then
    echo "Certificates already exist in ${PRIVATE_DIR}."
    echo "To regenerate, remove server-key.pem and server-cert.pem and run again."
    exit 0
fi

echo "Generating self-signed certificate and private key..."
openssl req -x509 -newkey rsa:4096 \
    -keyout "${KEY_FILE}" \
    -out "${CERT_FILE}" \
    -sha256 -days 3650 -nodes \
    -subj "/CN=qrdm"

chmod 600 "${KEY_FILE}"
chmod 644 "${CERT_FILE}"

echo "Generated:"
echo "  Private key: ${KEY_FILE}"
echo "  Certificate: ${CERT_FILE}"

