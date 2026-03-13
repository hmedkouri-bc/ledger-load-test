# Ledger Load Test

Load testing suite for the Nabu Ledger gRPC API, built for the **Flutterwave RFQ PoC**.

Validates that Ledger can sustain Flutterwave's transaction volume (30 RPS peak, 8,000 txn/day) without degrading existing workloads.

## Success Criteria

- Ledger debit latency (p99) < 100ms
- Impact on existing workloads < 5% latency increase
- Tested at 30 RPS peak against staging

## Quick Start

```bash
# Setup
make install
make proto

# Run unit tests
make test

# Run a quick connectivity check (1 user, 30s)
make run-balance CONFIG=config/local.yaml

# Run the full mixed workload with web UI
make run-ui CONFIG=config/staging.yaml
```

## Scenarios

| Scenario | Command | Description |
|----------|---------|-------------|
| Balance check | `make run-balance` | 100% `userAccountBalance` — isolate read perf |
| Append | `make run-append` | 100% `append` — isolate write perf |
| Mixed workload | `make run-mixed` | 70% balance / 30% append — realistic RFQ sim |
| Stress test | `make run-stress` | Mixed at 150 RPS — find breaking point |

## Load Profiles

- **FlutterwaveLoadShape**: Ramp to 6 users (baseline), spike to 30 (peak), cool-down. ~17 min total.
- **StressTestShape**: Step ramp 0→150 users in increments of 10, 60s per step.
- **StabilityLoadShape**: 24h sustained 6 RPS with 30 RPS spikes every 30 min.

## Docker (Distributed Mode)

```bash
docker compose up --build --scale worker=4
```

Open http://localhost:8089 for the Locust web UI.

## Configuration

Edit `config/staging.yaml` or override with env vars:

```bash
LEDGER_HOST=my-host LEDGER_PORT=443 LEDGER_TLS=true make run-mixed
```

## Project Structure

```
src/                  Core modules (config, payloads, gRPC client, UUID utils)
locustfiles/          Locust scenarios and base GrpcUser
proto/ledger/         Proto definitions
generated/            Auto-generated gRPC stubs (gitignored)
config/               YAML config files
tests/                Unit tests
```
