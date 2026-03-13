FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml .
COPY proto/ proto/
COPY scripts/ scripts/

RUN pip install --no-cache-dir grpcio-tools>=1.60 grpclib>=0.4.7 && \
    bash scripts/generate_proto.sh

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN apt-get update && apt-get install -y --no-install-recommends socat openssl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir locust>=2.20 grpclib>=0.4.7 protobuf>=4.25 pyyaml>=6.0

COPY --from=builder /app/generated/ generated/
COPY src/ src/
COPY locustfiles/ locustfiles/
COPY config/ config/

COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONPATH=.:generated

ENTRYPOINT ["/entrypoint.sh"]
