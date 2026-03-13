FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml .
COPY proto/ proto/
COPY scripts/ scripts/

RUN pip install --no-cache-dir grpcio-tools>=1.60 && \
    bash scripts/generate_proto.sh

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir locust>=2.20 grpcio>=1.60 protobuf>=4.25 pyyaml>=6.0

COPY --from=builder /app/generated/ generated/
COPY src/ src/
COPY locustfiles/ locustfiles/
COPY config/ config/

ENV PYTHONPATH=.:generated

ENTRYPOINT ["locust"]
