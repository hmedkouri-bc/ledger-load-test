# Flutterwave Crypto RFQ Service — Technical Specification

| Field | Value |
|:------|:------|
| **Status** | Draft |
| **Authors** | Sami Youness, Hicham Medkouri, Amaury Lamy |
| **Date** | March 12, 2026 |
| **Stakeholders** | Al Turnbull, Marc Sischka, Brian Cooper, Swati Bhargava |
| **Supersedes** | prd.md (exploratory document) |

---

## 1. Executive Summary

This document specifies the design, API contract, risk model, and delivery plan for a crypto RFQ (Request for Quote) execution service enabling Flutterwave to obtain executable crypto prices and execute spot trades against Blockchain.com as counterparty.

**Architectural decision:** The RFQ model has been selected over the order book model. Rationale:

- Flutterwave's use case is not latency-sensitive (~250ms+ RTT Africa↔Tokyo is acceptable).
- RFQ provides deterministic pricing with no slippage risk for the client.
- Significantly simpler infrastructure — no need to deploy the full Exchange matching engine on AWS.
- Better alignment with existing QMS hedging flow.
- Easier to control risk exposure via quote validity windows and last-look.

---

## 2. Requirements

### 2.1 Functional Requirements

| ID | Requirement | Priority |
|:---|:------------|:---------|
| FR-01 | Flutterwave can request a firm quote for a given pair, side, and amount | Must |
| FR-02 | Flutterwave can execute a previously received quote within its validity window (60 seconds) | Must |
| FR-03 | Flutterwave can retrieve historical trades with pagination and filtering | Must |
| FR-04 | Flutterwave can query the status of a specific quote | Must |
| FR-05 | Flutterwave can query the details of a specific trade | Must |
| FR-06 | System applies last-look validation before confirming execution | Must |
| FR-07 | Fees are applied as a hard-coded spread per pair | Must |
| FR-08 | Hedging executes via the existing QMS flow (no new hedging logic) | Must |
| FR-09 | System enforces pre-trade collateral balance checks | Must |
| FR-10 | System sends notifications when collateral approaches a threshold | Should |
| FR-11 | Health endpoint for operational monitoring | Must |

### 2.2 Non-Functional Requirements

| ID | Requirement | Target |
|:---|:------------|:-------|
| NFR-01 | Quote response latency (p99) | < 500ms |
| NFR-02 | Execution response latency (p99) | < 1000ms |
| NFR-03 | Availability | 99.9% (excludes planned maintenance) |
| NFR-04 | Daily transaction capacity | 8,000 trades/day (~6 RPS average, 30 RPS peak) |
| NFR-05 | Quote validity | 60 seconds |
| NFR-06 | Trade data retention | 7 years (regulatory) |
| NFR-07 | API rate limit | 20 requests/second per API key |

### 2.3 Trading Parameters

| Parameter | Value | Source |
|:----------|:------|:-------|
| Minimum ticket size | $500 equivalent | Confirmed (call 09/03/2026) |
| Maximum ticket size | $1,000,000 equivalent | Confirmed (call 09/03/2026) |
| Daily volume | 4,000–8,000 transactions | Flutterwave estimate |
| Quote denomination | Stablecoins only (no fiat) | Confirmed |
| Trading hours | 24/7 | Confirmed (call 09/03/2026) |
| Settlement frequency | Once per day, batched | Confirmed (Brian Cooper, call 09/03/2026) |
| Settlement chains | Polygon, Base, Solana | Flutterwave to confirm final list |
| Settlement model | Single master wallet, batched | Confirmed (call 09/03/2026) |
| Coin list | BTC minimum; full list TBD | Nkem Abuah to provide list + roadmap |
| Collateral model | Prefunding first, credit later | Confirmed (call 09/03/2026) |
| Indicative pricing | Deferred to Phase 2 (currently uses CoinGecko; production pricing requires MRE integration) | Agreed (call 09/03/2026) |

### 2.4 Counterparty Model

- **Legal/trading counterparty:** Flutterwave (single entity).
- **End customers:** Not visible to our systems. Flutterwave aggregates and faces us directly.
- **Reporting:** Trade-by-trade to Flutterwave. No end-customer-level reporting.

---

## 3. Architecture

### 3.1 High-Level Design

```
┌──────────────┐       HTTPS/mTLS        ┌──────────────────┐
│  Flutterwave │ ──────────────────────── │  API Gateway      │
│   (Africa)   │                          │  (region TBD)     │
└──────────────┘                          └────────┬─────────┘
                                                   │
                                          ┌────────▼─────────┐
                                          │  RFQ Service      │
                                          │  (containerized)  │
                                          │                   │
                                          │  - Quote Engine   │
                                          │  - Execution      │
                                          │  - Trade Store    │
                                          │  - Collateral Mgr │
                                          └──┬──────┬────┬───┘
                                             │      │    │
                              ┌──────────────┘      │    └──────────────┐
                              ▼                     ▼                   ▼
                    ┌─────────────────┐   ┌─────────────┐    ┌─────────────────┐
                    │  QMS / Hedging  │   │  PostgreSQL  │    │  Nabu Ledger    │
                    │  (AWS - Tokyo)  │   │  (managed)   │    │  (existing)     │
                    └─────────────────┘   └─────────────┘    └─────────────────┘
```

**Key decisions:**

- **Region & Cloud Provider:** TBD — to be decided in collaboration with SRE. Two options under consideration:
  - **AWS** — co-located with QMS and hedging infrastructure, minimizing latency on the critical pricing path. However, SRE's operational tooling, CI/CD, and on-call processes are built around GCP.
  - **GCP** — aligned with SRE's cloud provider of choice, benefiting from existing operational maturity (monitoring, deployment pipelines, incident response). Introduces cross-cloud latency to QMS on AWS.
  - This decision must be made during the PoC phase (see Section 6) with SRE input. The PoC should measure cross-cloud latency if GCP is selected.
- **Compute:** Containerized service (ECS Fargate on AWS or Cloud Run/GKE on GCP, depending on cloud provider decision). No Exchange deployment required; the RFQ service is a standalone microservice.
- **Database:** Managed PostgreSQL (RDS or Cloud SQL, depending on cloud provider decision) — quotes, trades.
- **Collateral:** Nabu Ledger (existing company ledger) — collateral balances, debits, and credits. Reuses existing infrastructure; requires load testing to validate capacity at Flutterwave volumes (see Section 6).
- **Hedging:** The RFQ service calls QMS in Tokyo via internal network. If deployed on GCP, this requires cross-cloud connectivity (GCP↔AWS) which adds latency and must be validated during PoC. This is the only cross-region call and occurs asynchronously after execution confirmation.

### 3.2 Request Flow

#### RFQ Flow

```
Flutterwave                  API Gateway              RFQ Service                QMS (Tokyo)
    │                            │                        │                          │
    │── POST /rfq ──────────────▶│                        │                          │
    │                            │── authenticate ───────▶│                          │
    │                            │                        │── check collateral       │
    │                            │                        │── get indicative price ──▶│
    │                            │                        │◀─ price ─────────────────│
    │                            │                        │── apply spread + fees    │
    │                            │                        │── store quote (TTL 60s)  │
    │◀─ 200: quote ──────────────│◀───────────────────────│                          │
    │                            │                        │                          │
```

#### Execution Flow

```
Flutterwave                  API Gateway              RFQ Service                QMS (Tokyo)
    │                            │                        │                          │
    │── POST /rfq/{id}/execute ─▶│                        │                          │
    │                            │── authenticate ───────▶│                          │
    │                            │                        │── validate quote (not expired, not used) │
    │                            │                        │── last-look check ──────▶│
    │                            │                        │◀─ confirm ──────────────│
    │                            │                        │── debit collateral       │
    │                            │                        │── persist trade          │
    │                            │                        │── mark quote consumed    │
    │◀─ 200: trade ──────────────│◀───────────────────────│                          │
    │                            │                        │── hedge (async) ─────────▶│
    │                            │                        │                          │
```

### 3.3 Collateral Management

**Lifecycle:**

1. Flutterwave pre-funds a collateral balance in stablecoins (off-platform transfer).
2. Operations team credits the balance in the system via an internal admin endpoint.
3. Each executed trade atomically debits the collateral balance.
4. When the balance falls below a configurable threshold (e.g., 20% of initial), the system emits an alert and optionally notifies Flutterwave via webhook.
5. Settlement occurs once daily: Operations reconciles, Flutterwave tops up, balance is credited.

**Collateral check timing:** At both quote creation (soft check — balance must be sufficient at quote time) and execution (hard check — atomic debit-or-reject).

**Ledger integration:** Collateral balances are managed through Nabu Ledger, the company's existing internal ledger service. The RFQ service calls Nabu Ledger for balance checks (soft reservation at quote time) and atomic debits (at execution time). This avoids building a separate collateral system and ensures consistency with existing financial infrastructure. Nabu Ledger must be load tested to confirm it can sustain Flutterwave's expected throughput (up to 8,000 transactions/day, 30 RPS peak) without degrading existing workloads.

**Phase 1:** Balance credits/resets are manual (Operations team via Nabu Ledger admin tooling).
**Phase 2:** Automated on-chain deposit detection.

### 3.4 Settlement Process

| Step | Actor | Action |
|:-----|:------|:-------|
| 1 | System | Generates daily settlement report (all trades since last settlement) |
| 2 | Operations | Reviews and confirms settlement amounts |
| 3 | Flutterwave | Sends net settlement amount to master wallet (Polygon, Base, or Solana) |
| 4 | Operations | Confirms on-chain receipt |
| 5 | Operations | Credits Flutterwave's collateral balance via admin API |

**Settlement chains:** Polygon, Base, Solana. Flutterwave to confirm preferred chain per settlement. We accept any of the three.

---

## 4. API Specification

### 4.1 Authentication

**Method:** HMAC-SHA256 request signing.

Every request must include:

| Header | Description |
|:-------|:------------|
| `X-API-Key` | Flutterwave's API key (identifies the client) |
| `X-Timestamp` | Unix epoch milliseconds (request must arrive within ±30 seconds) |
| `X-Signature` | HMAC-SHA256(secret, `{timestamp}.{method}.{path}.{body}`) |

Requests outside the ±30 second window are rejected (replay protection). API keys are rotatable via an Operations admin process. Each API key maps to a rate limit policy and collateral account.

### 4.2 Common Response Envelope

All responses follow this structure:

```json
{
  "status": "ok" | "error",
  "data": { ... },
  "error": {
    "code": "STRING_ERROR_CODE",
    "message": "Human-readable description"
  },
  "request_id": "uuid"
}
```

`request_id` is a correlation ID echoed from the `X-Request-Id` header if provided, otherwise server-generated.

### 4.3 Error Codes

| Code | HTTP Status | Meaning |
|:-----|:------------|:--------|
| `INVALID_REQUEST` | 400 | Malformed request body or missing required fields |
| `INVALID_PAIR` | 400 | Unsupported trading pair |
| `INVALID_AMOUNT` | 400 | Amount outside min/max bounds |
| `INVALID_SIDE` | 400 | Side must be `BUY` or `SELL` |
| `QUOTE_NOT_FOUND` | 404 | Quote ID does not exist |
| `TRADE_NOT_FOUND` | 404 | Trade ID does not exist |
| `QUOTE_EXPIRED` | 410 | Quote validity window has elapsed |
| `QUOTE_ALREADY_EXECUTED` | 409 | Quote has already been consumed |
| `INSUFFICIENT_COLLATERAL` | 422 | Collateral balance insufficient for this trade |
| `EXECUTION_REJECTED` | 422 | Last-look rejected the execution (price moved beyond tolerance) |
| `PRICE_UNAVAILABLE` | 503 | Unable to obtain a price from QMS |
| `RATE_LIMIT_EXCEEDED` | 429 | Request rate limit exceeded |
| `UNAUTHORIZED` | 401 | Invalid API key or signature |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

### 4.4 Endpoints

#### `POST /v1/rfq`

Request a firm quote.

**Request:**

```json
{
  "pair": "BTC-USDT",
  "side": "BUY",
  "amount": "0.5",
  "amount_currency": "BASE",
  "client_reference_id": "fw-order-abc-123"
}
```

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `pair` | string | Yes | Trading pair (format: `{BASE}-{QUOTE}`) |
| `side` | string | Yes | `BUY` or `SELL` (from Flutterwave's perspective) |
| `amount` | string | Yes | Decimal amount as string (avoids floating point) |
| `amount_currency` | string | Yes | `BASE` or `QUOTE` — which asset the amount is denominated in |
| `client_reference_id` | string | No | Flutterwave's internal reference. Stored but not used for idempotency. |

**Response (200):**

```json
{
  "status": "ok",
  "data": {
    "quote_id": "q-550e8400-e29b-41d4-a716-446655440000",
    "pair": "BTC-USDT",
    "side": "BUY",
    "price": "67542.50",
    "base_amount": "0.5",
    "quote_amount": "33771.25",
    "fee_amount": "33.77",
    "fee_currency": "USDT",
    "total_amount": "33805.02",
    "total_currency": "USDT",
    "expires_at": "2026-03-12T14:01:00Z",
    "created_at": "2026-03-12T14:00:00Z"
  },
  "request_id": "req-abc-123"
}
```

**Idempotency:** Not idempotent. Each call generates a new quote. Flutterwave should not retry on timeout — instead query `GET /v1/rfq/{id}` or simply request a new quote.

---

#### `POST /v1/rfq/{quoteId}/execute`

Execute a previously received quote.

**Request:**

```json
{
  "client_reference_id": "fw-exec-abc-123"
}
```

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `client_reference_id` | string | No | Flutterwave's execution reference |

**Response (200):**

```json
{
  "status": "ok",
  "data": {
    "trade_id": "t-660e8400-e29b-41d4-a716-446655440000",
    "quote_id": "q-550e8400-e29b-41d4-a716-446655440000",
    "pair": "BTC-USDT",
    "side": "BUY",
    "price": "67542.50",
    "base_amount": "0.5",
    "quote_amount": "33771.25",
    "fee_amount": "33.77",
    "fee_currency": "USDT",
    "total_amount": "33805.02",
    "total_currency": "USDT",
    "status": "COMPLETED",
    "client_reference_id": "fw-exec-abc-123",
    "executed_at": "2026-03-12T14:00:30Z"
  },
  "request_id": "req-def-456"
}
```

**Idempotency:** Idempotent on `quoteId`. Executing the same quote twice returns the original trade (HTTP 200), not an error. This is critical — if Flutterwave's connection drops after we confirm but before they receive the response, retry must be safe.

**State transitions for a quote:**

```
PENDING ──(execute)──▶ EXECUTED
PENDING ──(timeout)──▶ EXPIRED
PENDING ──(last-look reject)──▶ REJECTED
```

---

#### `GET /v1/rfq/{quoteId}`

Retrieve the status of a quote.

**Response (200):**

```json
{
  "status": "ok",
  "data": {
    "quote_id": "q-550e8400-e29b-41d4-a716-446655440000",
    "pair": "BTC-USDT",
    "side": "BUY",
    "price": "67542.50",
    "base_amount": "0.5",
    "quote_amount": "33771.25",
    "fee_amount": "33.77",
    "fee_currency": "USDT",
    "total_amount": "33805.02",
    "total_currency": "USDT",
    "quote_status": "EXECUTED",
    "trade_id": "t-660e8400-e29b-41d4-a716-446655440000",
    "expires_at": "2026-03-12T14:01:00Z",
    "created_at": "2026-03-12T14:00:00Z"
  },
  "request_id": "req-ghi-789"
}
```

`quote_status` is one of: `PENDING`, `EXECUTED`, `EXPIRED`, `REJECTED`.
`trade_id` is only present when `quote_status` is `EXECUTED`.

---

#### `GET /v1/trades/{tradeId}`

Retrieve details of a specific trade.

**Response (200):**

```json
{
  "status": "ok",
  "data": {
    "trade_id": "t-660e8400-e29b-41d4-a716-446655440000",
    "quote_id": "q-550e8400-e29b-41d4-a716-446655440000",
    "pair": "BTC-USDT",
    "side": "BUY",
    "price": "67542.50",
    "base_amount": "0.5",
    "quote_amount": "33771.25",
    "fee_amount": "33.77",
    "fee_currency": "USDT",
    "total_amount": "33805.02",
    "total_currency": "USDT",
    "status": "COMPLETED",
    "client_reference_id": "fw-exec-abc-123",
    "executed_at": "2026-03-12T14:00:30Z",
    "settlement_status": "PENDING",
    "settlement_batch_id": null
  },
  "request_id": "req-jkl-012"
}
```

`settlement_status`: `PENDING`, `SETTLED`.

---

#### `GET /v1/trades`

List trades with filtering and cursor-based pagination.

**Query parameters:**

| Parameter | Type | Required | Description |
|:----------|:-----|:---------|:------------|
| `from` | ISO 8601 | No | Start of time range (inclusive) |
| `to` | ISO 8601 | No | End of time range (exclusive) |
| `pair` | string | No | Filter by trading pair |
| `status` | string | No | Filter by trade status |
| `limit` | integer | No | Page size (default 50, max 200) |
| `cursor` | string | No | Opaque cursor from previous response |

**Response (200):**

```json
{
  "status": "ok",
  "data": {
    "trades": [ ... ],
    "pagination": {
      "next_cursor": "eyJsYXN0X2lkIjoiMTIzIn0=",
      "has_more": true
    }
  },
  "request_id": "req-mno-345"
}
```

Cursor is an opaque base64-encoded token. Trades are returned in reverse chronological order (`executed_at` descending).

---

#### `GET /v1/health`

**Response (200):**

```json
{
  "status": "ok",
  "data": {
    "service": "healthy",
    "dependencies": {
      "database": "healthy",
      "qms": "healthy"
    }
  }
}
```

Returns HTTP 503 if any dependency is unhealthy.

---

## 5. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|:---|:-----|:-----------|:-------|:-----------|:------|
| R-01 | **QMS latency/unavailability from eu-west-1** — Cross-region call to Tokyo fails or exceeds latency budget | Medium | High | Circuit breaker with fast-fail (return `PRICE_UNAVAILABLE`). PoC must measure actual latency distribution. Fallback: cache recent prices with wider spread for degraded mode. | Engineering |
| R-02 | **Hedge failure after trade confirmation** — Trade confirmed to Flutterwave but hedge leg fails or fills at worse price | Medium | High | Last-look validates price freshness before confirming. Hedge tolerance bands defined per pair. If hedge fails, trade still stands (we absorb the risk) and alert fires for manual intervention. Daily P&L reconciliation catches drift. | Trading / Engineering |
| R-03 | **Collateral exhaustion between quote and execution** — Balance sufficient at quote time but insufficient at execution time (concurrent requests) | Medium | Medium | Soft reservation at quote time (decrements available balance, released on expiry). Hard atomic debit at execution. Concurrent quotes compete for the same collateral — Flutterwave must manage their own request flow. | Engineering |
| R-04 | **Quote flooding / abuse** — Flutterwave (or attacker) requests thousands of quotes without executing, gaining free price discovery or exhausting collateral reservations | Low | Medium | Rate limit on quote creation (separate from execution rate limit). Monitoring on quote-to-execution ratio. If ratio drops below threshold, alert and optionally reduce rate limit. Soft reservation means collateral is temporarily locked but released on expiry. | Engineering |
| R-05 | **Settlement chain failure** — On-chain settlement on Polygon/Base/Solana fails or is delayed | Medium | Medium | Settlement is manual in Phase 1, giving Operations time to retry or switch chains. Multiple chain options provide redundancy. Clear escalation path if settlement is delayed >24h. | Operations |
| R-06 | **Data breach / unauthorized API access** — API key compromise or endpoint exposure | Low | Critical | HMAC signing (not bearer tokens — key never transmitted). IP allowlisting. WAF rules on API Gateway. Key rotation procedure with zero-downtime overlap period. Audit log on all authenticated requests. | Security / Engineering |
| R-07 | **Flutterwave volume exceeds capacity** — Daily transactions exceed 8,000 or burst rate exceeds system capacity | Low | Medium | Auto-scaling on ECS. Rate limits enforce per-client caps. Load test to 5x expected volume during PoC. | Engineering |
| R-08 | **Regulatory/compliance change** — New requirements on record-keeping, reporting, or counterparty obligations | Low | High | 7-year trade data retention from day one. All trades immutably stored with full audit trail. Compliance team engaged during design phase. | Legal / Compliance |
| R-09 | **Price manipulation via timing** — Flutterwave executes only favorable quotes (adverse selection) | Medium | Medium | Last-look with configurable tolerance band per pair. Monitoring on execution rate vs. price movement direction. If adverse selection is detected, widen spread. | Trading |
| R-10 | **Operational error on collateral reset** — Manual balance credit is incorrect (too high/too low) | Medium | Medium | Four-eyes principle on collateral adjustments. Admin API requires dual approval. All adjustments logged with before/after balances. Daily reconciliation report. | Operations |
| R-11 | **Cloud provider conflict (AWS vs. GCP)** — Deploying on AWS optimizes for QMS latency but lacks SRE operational support; deploying on GCP aligns with SRE but introduces cross-cloud latency and networking complexity | High | High | Evaluate both options during PoC with concrete latency measurements. Involve SRE early to assess operational cost of supporting AWS if selected. If GCP is chosen, validate that cross-cloud latency stays within budget and establish cross-cloud connectivity (e.g., Cloud Interconnect or VPN). Decision must have SRE sign-off. | Engineering / SRE |
| R-12 | **Nabu Ledger capacity under combined load** — Flutterwave volume (up to 30 RPS peak) degrades Nabu Ledger performance for existing consumers | Medium | High | Load test during PoC on staging with realistic traffic mix (Flutterwave + existing workloads). If capacity is insufficient: evaluate dedicated Nabu Ledger instance for Flutterwave, or request scaling from Ledger team. PoC is a hard gate — no go without passing load test criteria. | Engineering / Ledger team |

---

## 6. Proof of Concept Plan

### 6.1 Objective

Validate the four highest-risk technical assumptions before committing to the full build:

1. **Cross-region latency** — Can we obtain a price from QMS (Tokyo) and return a quote to eu-west-1 within the latency budget?
2. **QMS integration** — Can we programmatically request and receive firm prices through the existing QMS API without manual intervention?
3. **Nabu Ledger capacity** — Can Nabu Ledger sustain Flutterwave's transaction volume (30 RPS peak, 8,000 txn/day) without degrading performance for existing workloads?
4. **Cloud provider decision** — AWS (co-located with QMS) vs. GCP (SRE's platform of choice). If GCP, what is the actual cross-cloud latency to QMS on AWS?
5. **Infrastructure viability** — Can we deploy and operate the service on the chosen cloud provider with managed PostgreSQL and an API gateway?

### 6.2 Scope

**In scope:**
- Deploy a minimal service on the target cloud provider (ECS Fargate if AWS, Cloud Run/GKE if GCP)
- API gateway with HMAC auth (single test API key)
- `POST /v1/rfq` endpoint that calls QMS and returns a quote (no execution, no persistence)
- Latency measurement: end-to-end (Flutterwave simulated → API gateway → service → QMS → response). If GCP is the candidate, measure cross-cloud (GCP→AWS) latency to QMS separately.
- Nabu Ledger load test: simulate Flutterwave's expected volume (balance checks + debits at 30 RPS peak, sustained 6 RPS average) against a staging instance, measuring latency and impact on existing workloads
- Managed PostgreSQL instance (verify connectivity, basic schema creation)
- Infrastructure-as-code (Terraform)
- Cloud provider recommendation with SRE input, based on measured latency and operational trade-offs

**Out of scope:**
- Execution flow
- Collateral management
- Trade persistence
- Production-grade monitoring
- WAF / IP allowlisting
- Settlement

### 6.3 Success Criteria

| Criterion | Target | Method |
|:----------|:-------|:-------|
| End-to-end quote latency (p99) | < 500ms | Load test from simulated Africa-region client |
| QMS price retrieval success rate | > 99.5% over 24h test | Continuous quote requests at 5 RPS for 24 hours |
| Nabu Ledger debit latency (p99) | < 100ms | Load test at 30 RPS peak against staging |
| Nabu Ledger impact on existing workloads | < 5% latency increase | Compare baseline vs. load test metrics on staging |
| GCP→AWS cross-cloud latency (if GCP) | < 150ms round-trip to QMS | Measured from GCP europe-west1 to QMS on AWS |
| Infrastructure deployment | Fully automated, repeatable | Single `terraform apply` brings up entire stack |
| Service stability | Zero crashes over 24h | Continuous load test |

### 6.4 Timeline

| Week | Milestone | Deliverable |
|:-----|:----------|:------------|
| 1 | Infrastructure setup | Terraform/CDK scripts for ECS, RDS, API Gateway. Service skeleton deployed. |
| 2 | QMS integration | Service calls QMS, returns quotes. Latency instrumentation in place. |
| 3 | Validation | 24h load test. Latency report. Go/no-go recommendation. |

**Team:** 1 backend engineer + 0.5 DevOps. Total PoC cost: ~$35k (labor) + ~$2k (AWS).

### 6.5 Go/No-Go Decision

At the end of Week 3, the PoC produces a report covering:

- Latency distribution (p50, p95, p99, max) for the full quote path
- Cross-cloud latency measurements (if GCP was tested)
- QMS availability and error rate
- Nabu Ledger load test results and impact assessment
- Cloud provider recommendation (AWS vs. GCP) with SRE sign-off
- Infrastructure complexity assessment
- Identified blockers or risks not previously anticipated
- Recommendation: proceed to full build / proceed with modifications / do not proceed

**Decision makers:** Al Turnbull, Marc Sischka, Brian Cooper.

---

## 7. Delivery Plan (Post-PoC)

Contingent on PoC go decision.

### 7.1 Team

| Role | Count | Responsibility |
|:-----|:------|:---------------|
| Backend engineer | 3 | RFQ service, execution, trade store, collateral management |
| DevOps / Infra | 1 | AWS infrastructure, CI/CD, monitoring, alerting |
| QA | 0.5 | Test plans, integration testing, load testing |
| Architect / PM | 0.5 | Technical oversight, Flutterwave coordination |

### 7.2 Phases

| Phase | Duration | Scope |
|:------|:---------|:------|
| **Design & Security Review** | 2 weeks | Detailed design review. Security review of auth model, API surface, network architecture. Threat modeling. |
| **Core Build** | 6–8 weeks | RFQ lifecycle, execution + last-look, trade persistence, collateral management, admin API, HMAC auth, error handling, all API endpoints per Section 4. |
| **Integration & Testing** | 3–4 weeks | QMS integration testing across regions. Load testing at 5x expected volume. Failure injection (QMS down, DB down, collateral exhaustion). Flutterwave sandbox integration. |
| **UAT & Hardening** | 2 weeks | Flutterwave connects to staging environment. Runbooks written. Alerting thresholds tuned. Key rotation tested. |
| **Go-Live** | 1 week | Canary rollout. Monitoring in war-room mode for first 48h. |

**Total: 14–17 weeks** (3.5–4.25 months) post-PoC.

### 7.3 Budget

| Item | Monthly | Duration | Total |
|:-----|:--------|:---------|:------|
| Backend (3 engineers) | $75,000 | 4 months | $300,000 |
| DevOps (1 engineer) | $20,000 | 4 months | $80,000 |
| QA (0.5) | $10,000 | 4 months | $40,000 |
| PM / Architect (0.5) | $10,000 | 4 months | $40,000 |
| PoC (completed prior) | — | — | $37,000 |
| **Total labor** | | | **$497,000** |

| Cloud Infrastructure (estimates, provider-dependent) | Monthly Estimate |
|:------------------------------------------------------|:-----------------|
| API Gateway + WAF | $3,000–5,000 |
| Compute (ECS Fargate / Cloud Run / GKE) | $4,000–7,000 |
| Managed PostgreSQL (Multi-AZ / HA) | $3,000–5,000 |
| Monitoring + logging | $1,500–3,000 |
| Cross-region / cross-cloud data transfer | $1,000–3,000 |
| **Total infra** | **$12,500–23,000/month** |

*Note: Cross-cloud data transfer (GCP↔AWS) is typically more expensive than intra-cloud. Final estimates depend on the cloud provider decision made during the PoC.*

---

## 8. Open Items

| ID | Item | Owner | Due |
|:---|:-----|:------|:----|
| OI-01 | Final list of supported trading pairs | Nkem Abuah (Flutterwave) | Before PoC start |
| OI-02 | Confirm settlement chain preferences per pair | Flutterwave | Before Core Build |
| OI-03 | Initial collateral amount | Flutterwave / Brian Cooper | Before Core Build |
| OI-04 | Collateral threshold for notifications (% of initial) | Brian Cooper / Marc Sischka | Before Core Build |
| OI-05 | Fee schedule per pair (hard-coded spread bps) | Trading / Marc Sischka | Before Core Build |
| OI-06 | Cloud provider decision (AWS vs. GCP) with SRE sign-off | Engineering / SRE | End of PoC |
| OI-07 | QMS API documentation and access credentials for PoC | QMS team | Before PoC start |
| OI-08 | Security review sign-off | Security team | End of Design phase |
| OI-09 | Legal review of Flutterwave counterparty agreement | Legal | Before Go-Live |
| OI-10 | Flutterwave IP ranges for allowlisting | Flutterwave | Before UAT |
| OI-11 | Reporting format requirements (trade-by-trade CSV? API only?) | Brian Cooper / Flutterwave | Before Core Build |
