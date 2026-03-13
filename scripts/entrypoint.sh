#!/bin/bash
set -e

# If TLS_PROXY_TARGET is set, start a socat TLS-terminating proxy.
# This lets gRPC connect over plaintext to localhost, avoiding BoringSSL issues.
if [ -n "$TLS_PROXY_TARGET" ]; then
    TLS_PROXY_PORT="${TLS_PROXY_PORT:-50051}"
    echo "Starting TLS proxy: localhost:${TLS_PROXY_PORT} -> ${TLS_PROXY_TARGET} (verify=0)"
    socat TCP-LISTEN:${TLS_PROXY_PORT},reuseaddr,fork \
        OPENSSL:${TLS_PROXY_TARGET},verify=0 &
    sleep 1
fi

exec locust "$@"
