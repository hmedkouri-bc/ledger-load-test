# Analysis: `service-brokerage` for Flutterwave RFQ

**Date:** 2026-03-12
**Author:** Hicham Medkouri (with Claude Code analysis)
**Purpose:** Evaluate whether the existing `service-brokerage` project (retail Wallet business) is suitable for implementing the Flutterwave Crypto RFQ service specified in `flutterwave-rfq-specification.md`.

---

## 1. Project Scale

| Metric | Value |
|--------|-------|
| Total Kotlin files | 615 |
| Total lines of Kotlin | ~83,500 |
| Service module (main) | 327 files / ~36,500 LOC |
| Service module (tests) | 79 files / ~33,000 LOC |
| DB migrations | 30 versions |
| Proto/gRPC endpoints | ~30 RPC methods |
| FSM states | 17 |
| FSM event types | 66 (multi-versioned) |
| FSM commands | 45+ |
| External service integrations | 15+ |

---

## 2. External Dependencies Inventory

This is the **biggest concern** against the requirement of minimizing external dependencies. The current service integrates with:

| # | External Service | Protocol | Used For | Needed for Flutterwave? |
|---|-----------------|----------|----------|------------------------|
| 1 | **Bakkt** | HTTP | Crypto execution (exchange) | **No** — QMS replaces this |
| 2 | **Feynman** | Streaming | Liquidity/quotes | **No** — QMS replaces this |
| 3 | **Nabu Gateway** | HTTP | User info, KYC, limits | **No** — Flutterwave is a single counterparty |
| 4 | **Payment Gateway** | gRPC | Card auth, capture, deposits | **No** — collateral model, not payment rails |
| 5 | **Ledger (Nabu Ledger)** | gRPC | Balance checks, debits, credits | **Yes** — collateral management |
| 6 | **Hot Wallet Service** | gRPC | Withdrawal address validation | **No** — no on-chain settlement in Phase 1 |
| 7 | **Fraud Service** | gRPC | Fraud detection | **No** — B2B counterparty, not retail |
| 8 | **Risk Engine** | Kafka | Fund reservation | **No** — replaced by Ledger collateral checks |
| 9 | **Mercury** | HTTP/gRPC | Exchange order book | **No** — RFQ not order book |
| 10 | **Price Service** | HTTP | Indicative prices | **Maybe** — or get from QMS directly |
| 11 | **Assets Service** | gRPC | Crypto metadata | **Minimal** — pair config only |
| 12 | **Experiment Service** | HTTP | Feature flags/A/B | **No** |
| 13 | **Consul** | Discovery | Service discovery for Akka cluster | **No** — overkill for RFQ |
| 14 | **Kafka** (3 producer topics) | Kafka | Event broadcasting | **Maybe** — for trade notifications |
| 15 | **Kafka** (2 consumer topics) | Kafka | Async responses | **No** |

**Only 1 of 15 external dependencies is needed.** You'd have to rip out or stub 14 integrations.

---

## 3. Architecture Mismatch Assessment

### What the Flutterwave RFQ needs vs. what this project provides

| RFQ Requirement | What this project has | Fit? |
|----------------|----------------------|------|
| **Stateless quote generation** (60s TTL) | Event-sourced FSM with 17 states, snapshots, recovery | Massive overkill |
| **Simple execute-or-expire** | Multi-phase coordinators (Reserve → Execute → Capture → Withdraw → Refund) | Massive overkill |
| **Single counterparty** (Flutterwave) | Per-user model with KYC, limits, fraud checks | Wrong model |
| **HMAC API auth** | gRPC-first with internal service auth | Need to build from scratch |
| **REST/JSON API** | gRPC primary, HTTP secondary (Undertow) | Partial — HTTP exists but secondary |
| **Collateral balance checks** | LedgerClient already integrated | Good fit |
| **Cursor-based trade pagination** | jOOQ + PostgreSQL repos exist | Good fit |
| **Fee as spread (bps)** | Complex fee system (FeeService, experiments, country-based, tiers) | Overkill but usable |
| **Last-look validation** | Not present — different execution model | Must build new |
| **QMS integration** | Not present — uses Bakkt/Feynman | Must build new |
| **Daily settlement reports** | Not present | Must build new |
| **24/7 availability** | Akka cluster with rolling deploys | Overkill but works |

### What you'd reuse

- **PostgreSQL + jOOQ + Flyway**: Database layer, migration tooling, connection pooling
- **LedgerClient**: Already wired — balance checks and debits
- **Gradle build setup**: Multi-module structure, nexus publishing, ktlint
- **Kamon/Datadog monitoring**: APM instrumentation
- **gRPC/Proto tooling** (if you chose gRPC, but the spec calls for REST)

### What you'd have to rip out

- The entire Akka actor system (cluster, sharding, persistence, projections, coordinators)
- All 10 effectful clients except Ledger
- All Kafka producers and consumers
- The 17-state FSM and all 66 event types
- Mercury module
- Recurring buy subsystem
- Watchlist subsystem
- External brokerage allocation subsystem
- Fraud/Risk Engine integration
- Payment Gateway integration

---

## 4. Honest Concerns

### 4.1 Accidental Complexity

This project carries **enormous accidental complexity** for the Flutterwave use case:

- **Event sourcing** with backward-compatible event versioning, snapshot retention, recovery handlers — all designed for long-running orders that can take days. RFQ quotes live 60 seconds.
- **Akka cluster sharding** with Consul discovery — designed for horizontal scaling of thousands of concurrent user sessions. Flutterwave is a single counterparty.
- **5 coordinator FSMs** as child actors — designed to orchestrate multi-party payment flows. RFQ has one flow: price → execute.

### 4.2 Operational Burden

- Running Akka cluster requires **Consul**, careful rolling deploy orchestration, split-brain resolution, and snapshot management.
- Event sourcing requires **indefinite backward compatibility** of journal events — every schema change forever.
- The test infrastructure requires embedded PostgreSQL, Akka test kits, and complex mock setups — 33K LOC of tests, most irrelevant to Flutterwave.

### 4.3 Onboarding Cost

Any engineer joining this project must understand:

- Akka Typed actors, cluster sharding, persistence
- Event sourcing patterns and event adapter chains
- The effectful client pattern with watchdog actors
- 17 FSM states with 45+ commands
- The coordinator hierarchy

This is a **steep learning curve** for a service that should be simple.

### 4.4 Risk of Regression

Adding Flutterwave functionality to this codebase means:

- **Shared database** — migrations affect both retail and Flutterwave
- **Shared DI container** — changes to BrokerageModule affect both
- **Shared deployment** — a Flutterwave bug could take down retail orders
- **Coupled release cycles** — can't deploy Flutterwave changes independently

### 4.5 API Surface Mismatch

The spec calls for **REST/JSON with HMAC auth**. This project is **gRPC-first**. You'd need to:

- Build a full HTTP layer (the current Undertow server is minimal/secondary)
- Implement HMAC-SHA256 request signing (not present)
- Implement the response envelope pattern (`status`, `data`, `error`, `request_id`)
- Build cursor-based pagination (different from gRPC streaming)

---

## 5. What You'd Actually Reuse (Honest Assessment)

If you fork/extend this project, you'd realistically reuse:

| Component | Lines (est.) | % of total |
|-----------|-------------|------------|
| Gradle build infrastructure | ~500 | 0.6% |
| Database module (jOOQ, Flyway, HikariCP) | ~2,000 | 2.4% |
| LedgerClient wiring | ~200 | 0.2% |
| Common utilities | ~500 | 0.6% |
| Monitoring/metrics setup | ~300 | 0.4% |
| **Total reusable** | **~3,500** | **~4%** |

You'd be **inheriting 96% dead weight** that must be understood, maintained, or ripped out.

---

## 6. Recommendation

### **Do NOT use this project for Flutterwave. Build a new, dedicated service.**

### Rationale

1. **Wrong architecture**: Event-sourced Akka FSM is the wrong tool for a request-response RFQ service. It introduces operational complexity (Consul, cluster management, event versioning) with zero benefit.

2. **14 of 15 external dependencies are unnecessary**: The requirement to minimize external dependencies is fundamentally incompatible with this codebase. Removing them would be more work than starting fresh.

3. **Blast radius**: Co-locating Flutterwave B2B trading with retail user order management creates coupling risk. Different SLAs, different counterparty models, different release cadences.

4. **Development speed**: A greenfield RFQ service with just PostgreSQL + LedgerClient + QMS could be built in 3-4 weeks (the PoC timeline). Adapting this project would take longer due to rip-out work, testing, and understanding the existing architecture.

5. **The spec is simple**: 6 endpoints, 2 tables (quotes, trades), 1 external dependency (Ledger), 1 new integration (QMS). This does not warrant an 83K LOC event-sourced actor system.

### What to reuse from this project (copy, don't extend)

- **Gradle build template**: Copy `build.gradle.kts`, `settings.gradle.kts`, nexus config
- **LedgerClient dependency**: Import `nabu-ledger.client` as a library dependency
- **Database patterns**: Copy the jOOQ codegen setup, Flyway migration structure, HikariCP config
- **Monitoring**: Copy Kamon/Datadog setup
- **CI/CD workflows**: Copy `.github/` workflows and adapt

This gives you the ~4% that's useful without the ~96% that's harmful.
