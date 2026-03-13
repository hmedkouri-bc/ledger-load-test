# Ledger Load Testing Project — Implementation Plan

## Context

The Flutterwave RFQ PoC requires validating that Nabu Ledger can sustain Flutterwave's transaction volume (30 RPS peak, 8,000 txn/day) without degrading existing workloads. The PoC success criteria from `flutterwave-rfq-specification.md`:

- Ledger debit latency (p99) < 100ms
- Impact on existing workloads < 5% latency increase
- Tested at 30 RPS peak against staging

This plan creates a **standalone Python project** using **Locust + grpcio** to load test the Ledger gRPC API.

---

## Project Structure

```
ledger-load-test/
├── README.md
├── pyproject.toml
├── Makefile
├── Dockerfile
├── docker-compose.yml
├── proto/
│   └── ledger/
│       ├── ledger_transaction.proto
│       └── ledger_balance.proto
├── generated/                        # gitignored, auto-generated stubs
│   └── ledger/
├── scripts/
│   └── generate_proto.sh
├── config/
│   ├── staging.yaml
│   └── local.yaml
├── src/
│   ├── __init__.py
│   ├── grpc_client.py                # Thin wrapper around generated stubs
│   ├── uuid_utils.py                 # UUID <-> UniqueID (high/low sint64)
│   ├── payload_factory.py            # Builds realistic requests
│   ├── config_loader.py              # YAML + env var config
│   └── load_shapes.py               # Custom Locust LoadTestShape classes
├── locustfiles/
│   ├── grpc_user.py                  # Base GrpcUser with timing/error reporting
│   ├── balance_check.py             # Scenario 1: balance checks only
│   ├── append_transaction.py        # Scenario 2: appends only
│   ├── mixed_workload.py            # Scenario 3: 70/30 balance/append
│   └── stress_test.py              # Scenario 4: 5x volume (150 RPS)
├── tests/
│   ├── test_uuid_utils.py
│   └── test_payload_factory.py
└── reports/
    └── .gitkeep
```

---

## gRPC API Under Test

Two proto services from the `nabu-ledger-client:1.4.80` JAR:

### LedgerTransactionService
- `ping(UniqueID) → UniqueID` — health check
- `append(AppendTransactionRequest) → AppendTransactionResponse` — atomic write
- `appendChecked(AppendTransactionRequest) → AppendTransactionResponse` — conditional write

### LedgerBalanceService
- `ping(UniqueID) → UniqueID` — health check
- `userAccountBalance(GetBalanceRequest) → GetBalanceResponse` — balance query

Proto files are extracted from the JAR at `/Users/hmedkouri/.gradle/caches/modules-2/files-2.1/com.blockchain.ledger/nabu-ledger-client/1.4.80/` (`ledger_transaction.proto`, `ledger_balance.proto`).

---

## Key Implementation Details

### 1. UUID ↔ UniqueID Encoding (`src/uuid_utils.py`)

Ledger uses a custom `UniqueID(sint64 high, sint64 low)` instead of string UUIDs. Based on the Kotlin client:

```python
def uuid_to_unique_id(u: uuid.UUID) -> tuple[int, int]:
    high = (u.int >> 64) & 0xFFFFFFFFFFFFFFFF
    low = u.int & 0xFFFFFFFFFFFFFFFF
    if high >= (1 << 63): high -= (1 << 64)
    if low >= (1 << 63): low -= (1 << 64)
    return high, low
```

Must be unit tested — incorrect encoding = silent failures.

### 2. Payload Factory (`src/payload_factory.py`)

**Balance check** (`GetBalanceRequest`):
- `owner`: random UUID from test pool → UniqueID
- `account`: `200500` (SIMPLEBUY_BALANCE)
- `max_offset`: 0 (latest)

**Append transaction** (`AppendTransactionRequest`):
- `TransactionProto` with:
  - `id`: fresh UUID
  - `account`: `200500` (SIMPLEBUY_BALANCE)
  - `origin`: `"LOADTEST_FLUTTERWAVE"`
  - `owner`: random test user UUID
  - `external_ref`: `"LOADTEST:{uuid}"` (for cleanup)
  - `legs`: 1 `TransactionLegProto` debiting from SIMPLEBUY_BALANCE to SIMPLEBUY_TRADE (200510)
  - `currency`: `"USDT"`, amount: random $500–$1M

Test user pool: 100 deterministically-seeded UUIDs to avoid single-account serialization.

Reference files for payload patterns:
- `service/src/main/kotlin/com/blockchain/brokerage/core/order/effectfulclients/LedgerSvcClient.kt`
- `service/src/main/kotlin/com/blockchain/brokerage/orders/ledger/LedgerClientUtils.kt`

### 3. Base GrpcUser (`locustfiles/grpc_user.py`)

Custom Locust `User` subclass that:
- Creates a gRPC channel per user in `on_start()`
- Wraps each RPC call to report timing via `self.environment.events.request.fire()`
- Catches `grpc.RpcError` and reports as Locust failures
- Supports plaintext and TLS channels (config-driven)

### 4. Load Shapes (`src/load_shapes.py`)

**FlutterwaveLoadShape** (Scenarios 1–3):
- 0–60s: ramp 0 → 6 users (warm-up)
- 60–300s: sustain 6 users (baseline)
- 300–360s: ramp 6 → 30 users (peak)
- 360–660s: sustain 30 users (peak hold, 5 min)
- 660–720s: ramp down 30 → 6
- 720–1020s: sustain 6 (cool-down)

**StressTestShape** (Scenario 4):
- Ramp 0 → 150 RPS in steps of 10, hold each step 60s

**StabilityLoadShape** (24h run):
- Sustained 6 RPS with periodic 30 RPS spikes every 30 min

### 5. Scenarios

| Scenario | File | Description | When to use |
|----------|------|-------------|-------------|
| 1 | `balance_check.py` | 100% `userAccountBalance` calls | Isolate read performance |
| 2 | `append_transaction.py` | 100% `append` calls | Isolate write performance |
| 3 | `mixed_workload.py` | 70% balance / 30% append | Realistic RFQ simulation |
| 4 | `stress_test.py` | Mixed at 150 RPS | Find breaking point |

### 6. Config (`config/staging.yaml`)

```yaml
ledger:
  host: "nabu-ledger-grpc.traefik"
  port: 443
  tls: true
  rpc_timeout_seconds: 5
test:
  user_pool_size: 100
  user_uuid_seed: 42
  origin: "LOADTEST_FLUTTERWAVE"
  external_ref_prefix: "LOADTEST:"
accounts:
  funding: 200500    # SIMPLEBUY_BALANCE
  trading: 200510    # SIMPLEBUY_TRADE
  fee: 200430        # SIMPLEBUY_FEE
currencies:
  primary: "USDT"
amounts:
  min: 500.0
  max: 1000000.0
```

Overridable via env vars: `LEDGER_HOST`, `LEDGER_PORT`, `LEDGER_TLS`.

### 7. Docker

Multi-stage Dockerfile (proto compile → slim runtime). `docker-compose.yml` with master + N workers for distributed mode.

---

## Implementation Sequence

| Step | What | Files |
|------|------|-------|
| 1 | Project scaffolding | `pyproject.toml`, `Makefile`, `.gitignore` |
| 2 | Proto files + generation script | `proto/ledger/*.proto`, `scripts/generate_proto.sh` |
| 3 | UUID utils + unit tests | `src/uuid_utils.py`, `tests/test_uuid_utils.py` |
| 4 | Config loader | `src/config_loader.py`, `config/*.yaml` |
| 5 | Payload factory + unit tests | `src/payload_factory.py`, `tests/test_payload_factory.py` |
| 6 | Base GrpcUser | `locustfiles/grpc_user.py` |
| 7 | Scenario 1 (balance check) | `locustfiles/balance_check.py` |
| 8 | Scenario 2 (append) | `locustfiles/append_transaction.py` |
| 9 | Load shapes | `src/load_shapes.py` |
| 10 | Scenario 3 (mixed) | `locustfiles/mixed_workload.py` |
| 11 | Scenario 4 (stress) | `locustfiles/stress_test.py` |
| 12 | Docker + compose | `Dockerfile`, `docker-compose.yml` |
| 13 | README | `README.md` |

---

## Verification

1. **Proto compilation**: `make proto` succeeds, stubs importable
2. **Unit tests**: `pytest tests/` — UUID conversion round-trips, payloads are valid
3. **Connectivity**: `locust -f locustfiles/balance_check.py --headless -u 1 -r 1 -t 10s` against staging — ping succeeds, balance check returns data
4. **Scenario correctness**: Run each scenario at 1 user for 30s, verify Locust reports 0 failures
5. **Full load test**: Run Scenario 3 with FlutterwaveLoadShape, verify p99 < 100ms at 30 RPS
