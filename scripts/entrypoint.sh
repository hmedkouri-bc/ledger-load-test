#!/bin/bash
set -e

# If TLS_PROXY_TARGET is set, start a socat TLS-terminating proxy.
# This lets gRPC connect over plaintext to localhost, avoiding BoringSSL issues.
# Uses openssl s_client with -alpn h2 so Traefik recognises HTTP/2 traffic.
if [ -n "$TLS_PROXY_TARGET" ]; then
    TLS_PROXY_PORT="${TLS_PROXY_PORT:-50051}"
    echo "Starting TLS proxy: localhost:${TLS_PROXY_PORT} -> ${TLS_PROXY_TARGET} (verify=0, alpn=h2)"
    socat TCP-LISTEN:${TLS_PROXY_PORT},reuseaddr,fork \
        "EXEC:openssl s_client -connect ${TLS_PROXY_TARGET} -alpn h2 -quiet -verify_quiet -no_ign_eof" &
    sleep 1
fi

exec locust "$@"
