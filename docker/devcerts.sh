#!/bin/sh
# dev: генерим self-signed серты, если их нет; потом запускаем что сказали
CERT="${SSL_CERTFILE:-/certs/cert.pem}"
KEY="${SSL_KEYFILE:-/certs/key.pem}"

if [ -n "$DEV_CERTS" ] && [ ! -f "$CERT" ]; then
  mkdir -p "$(dirname "$CERT")"
  echo "dev: генерирую self-signed сертификат -> $CERT"
  openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
    -keyout "$KEY" -out "$CERT" \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1
fi

exec "$@"
