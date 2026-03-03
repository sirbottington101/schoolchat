#!/bin/bash
# Generate self-signed TLS certificates for development.
# For production, use Let's Encrypt or a real CA.

CERT_DIR="./nginx/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "$CERT_DIR/privkey.pem" \
    -out "$CERT_DIR/fullchain.pem" \
    -subj "/CN=schoolchat.local/O=SchoolChat/C=AU"

echo "Self-signed certificates generated in $CERT_DIR/"
echo "  - fullchain.pem (certificate)"
echo "  - privkey.pem   (private key)"
echo ""
echo "For production, replace these with real certificates."
