**Institutional Engineering:**   
**Flutterwave opportunity**

| To: | [Al Turnbull](mailto:al@blockchain.com)[Marc Sischka](mailto:msischka@blockchain.com)[Brian Cooper](mailto:bcooper@blockchain.com) |
| :---- | :---- |
| **From:**  | [Sami Youness](mailto:syouness@blockchain.com)[Hicham Medkouri](mailto:hmedkouri@blockchain.com)[Amaury Lamy](mailto:alamy@blockchain.com) |
| **Date**: | January 22, 2026 |
| **Subject**: | Crypto Price & Execution Integration with Flutterwave |
| **Ref**: | Project exploration |
| **Action Required:** | Yes |

---

## Action Log

| Date / Stage | Action Taken | Owner(s) |
| :---- | :---- | :---- |
| Project exploration | Internal exploratory meeting held to assess feasibility of a crypto execution solution for Flutterwave: [Oliver Clifford](mailto:oclifford@blockchain.com)[Brian Cooper](mailto:bcooper@blockchain.com)[Sami Youness](mailto:syouness@blockchain.com)[Hicham Medkouri](mailto:hmedkouri@blockchain.com)[Amaury Lamy](mailto:alamy@blockchain.com) | [Brian Cooper](mailto:bcooper@blockchain.com) |
| Project exploration | Organize meeting with Flutterwave technical team | [Brian Cooper](mailto:bcooper@blockchain.com) |
| 03/03/2026 | Engineering estimate added to the the appendix | [Amaury Lamy](mailto:alamy@blockchain.com) |
|  |  |  |
|  |  |  |

## 

## 

## Introduction

Flutterwave is a Nigerian-founded global payments technology company that enables businesses to accept and make payments across Africa and internationally. Its platform supports merchants, financial institutions, and enterprises with APIs for payments, payouts, and financial services, with a strong focus on scalability and regional coverage.

This document outlines a proposed commercial and technical opportunity to provide crypto price discovery and electronic execution services to Flutterwave, enabling them to access executable crypto liquidity across multiple pairs denominated exclusively in stablecoins.

## 

## 2\. Project Overview

Flutterwave has expressed interest in accessing electronic execution for approximately 50 crypto trading pairs, all denominated in stablecoins (no fiat exposure). The execution flow is expected to be fully electronic, with Flutterwave acting as the direct counterparty to our platform, rather than their underlying end customers.

Key constraints and context:

* No public QMS API currently exists.  
* A public API does exist on the Exchange.  
* All Exchange components are now containerized using Docker, enabling cloud deployment.  
* Execution is expected to occur via order book interaction, not RFQ-style quoting.

## 3\. Proposed Solution Architecture

### 3.1 High-Level Design

The proposed solution is to deploy the Exchange infrastructure on AWS, colocated or geographically close to *QMS* *Advanced trading (QMS)* engine.

This approach minimizes latency and simplifies internal connectivity between *QMS* and the *BCX Exchange.*

Flutterwave would:

1. Receive a request from its customer.  
2. Translate this request into an order according to the Exchange API specification.  
3. Submit the order directly to the Exchange.

Meanwhile:

* *QMS* would publish liquidity to the Exchange order book.  
* Flutterwave’s orders would match against QMS-provided liquidity.  
* Trades would only execute after pre-trade balance validation by the Exchange.

### 3.2 Execution & Counterparty Model

* Legal / trading counterparty: Flutterwave  
* Underlying customers: Not directly visible to our systems  
* Execution model: Order-based matching on the Exchange  
* Pre-trade controls: Flutterwave (collateral) balance checks enforced by the Exchange

From our perspective, Flutterwave is the sole counterparty, simplifying:

* Risk management  
* Operational processes including settlement and collateral management  
* Compliance and reporting

## 4\. Balance & Collateral Management

### 4.1 Balance Representation

The Exchange has native functionality to validate balances before matching orders. The open question is how Flutterwave balances should be represented.

Proposed approach:

* Flutterwave provides a collateral balance in stablecoins.  
* A corresponding balance is configured on the Exchange.  
* Each executed trade consumes from this balance.

### 4.2 Settlement & Balance Reset

* As available balance approaches a predefined threshold, Flutterwave is notified.  
* A settlement occurs off-exchange.  
* The Exchange balance is manually reset to reflect the updated collateral.  
* In the initial phase, this reset process is expected to be manual, with automation considered later.

This model provides strong exposure control while allowing a relatively fast initial deployment.

## 5\. Points of Attention & Open Items

### 5.1 Trading Universe

* Final list of crypto pairs (approximately 50 expected).  
* Confirmation that all pairs are stablecoin-denominated.  
* Identification of base and quote assets.

### 5.2 Trade Size Parameters

* Typical minimum ticket size (e.g. retail-sized vs institutional minimums).  
* Expected maximum trade size (e.g. $100K, $500K, $1M+ equivalent).  
* Distribution of expected order sizes.

These inputs directly affect liquidity provisioning, risk limits, and system tuning.

### 

### 5.3 Balance & Settlement Operations

* Initial collateral amount.  
* Settlement frequency (daily, intraday, or threshold-based).  
* Operational ownership of balance resets.  
* Long-term automation requirements.

### 5.4 API & Integration Responsibilities

* Confirmation that Flutterwave will code directly to the Exchange API specification.  
* Order lifecycle handling (submission, cancellation, error handling).  
* Authentication, rate limits, and monitoring expectations.

### 5.5 Security Considerations

Security is a critical element of this project.

* Exposing a public-facing API increases the attack surface.  
* Secure endpoints must be provided to Flutterwave, including:  
  * Strong authentication and authorization mechanisms  
  * Network-level protections  
  * Monitoring and alerting

* Security requirements must be designed and validated early in the project lifecycle, not as a later add-on.

Any decision to proceed should include a dedicated security workstream from the outset.

### 

### 5.6 Infrastructure & Deployment Complexity

There is a non-trivial infrastructure effort associated with this proposal.

Key considerations:

* The Exchange has never been deployed on AWS before.  
* Current production deployment exists in LD4.  
* The Exchange consists of multiple tightly-coupled components, including:

  * Matching Engine  
  * Risk Engine  
  * API Gateway  
  * QMS components

This introduces:

* Architectural complexity  
* Deployment risk  
* New operational requirements (monitoring, scaling, failover)

If the opportunity is pursued, infrastructure design and cloud deployment work must begin early, in parallel with commercial and integration discussions.

## 6\. Summary

This proposal outlines a viable path to providing Flutterwave with secure, electronic crypto execution via an Exchange-based order book model. The approach leverages existing Exchange capabilities while introducing new infrastructure and security requirements due to cloud deployment and public API exposure.

# Appendix 

## Engineering Estimation 

### Goal and scope

Enable Flutterwave to request prices (RFQ), execute trades, and retrieve trade history via authenticated, rate-limited APIs, with hedging executed exactly as per the existing QMS flow.

### In scope

* Public-facing API layer (AWS API Gateway) for Flutterwave  
* Authentication \+ authorization for all endpoints  
* RFQ automation (no manual OTC intervention)  
* Quote generation \+ execution flow (spot only)  
* Trade persistence \+ retrieval API  
* Integration to existing hedging/QMS mechanisms  
* Monitoring, alerting, logging, and operational runbooks  
* Basic customer controls: rate limits, IP allowlisting (if desired), per-API key policies

### Out of scope (explicit)

* Banking rails  
* Balance / position endpoints  
* Ledger implementation  
* Blockchain balance checks  
* Automated settlement (Middle Office handles settlement as today)  
* Dynamic fee schedules (fees hard-coded)  
* Latency-sensitive architecture (regional routing/edge optimization)

### Assumptions (baseline)

1. Flutterwave can face MTM as counterparty  
2. No blockchain balance check; risk is managed via credit line, with no “credit check” gating at execution time  
3. Fees / customer spreads are hard-coded  
4. Hedging same as existing QMS flow (no new hedging logic)  
5. Flutterwave authenticates via an API Gateway; existing blockchain gateway is not reusable  
6. Use AWS API Gateway for rate limiting \+ security  
7. Not latency sensitive; \~250ms RTT between “Africa API Gateway” and “Tokyo hedging” is acceptable per RFQ  
8. Quote validity: 60 seconds  
9. Ticket size:  
   * Minimum: $500  
   * Max ticket: $1m  
   * Volume: 4,000–8,000 daily transactions  
10. Settlement not automated (Middle Office processes as today)  
11. RFQs are fully automated; no manual RFQ to OTC desk  
12. No position/balance because spot only and no ledger

### Proposed API surface (what we need to build)

### Authentication & access control (all endpoints)

* API key / OAuth2 / mTLS (pick one; AWS supports multiple patterns)  
* Per-customer rate limits and quotas  
* Request signing / replay protection (recommended)  
* Auditable identity on every request

### Endpoints

1. Submit RFQ  
    `POST /rfq`  
    Inputs: side, base/quote, amount (or notional), settlement currency, client reference id, optional constraints  
    Output: quote id, price, expiry timestamp, fees (hard-coded), total amount  
2. Execute RFQ  
    `POST /rfq/{quoteId}/execute`  
    Output: trade id, executed price, timestamps, fees, settlement instructions reference  
3. Retrieve trades  
    `GET /trades?from=&to=&status=&limit=&cursor=`  
    Output: paginated trades list  
4. (Optional but usually required operationally)  
   * `GET /rfq/{quoteId}` (quote status)  
   * `GET /trades/{tradeId}` (trade details)  
   * `GET /health` (internal / allowlisted)

## 

## Engineering Work Breakdown (Effort by Stream)

### API Gateway \+ Security Layer

Scope

* AWS API Gateway setup  
* Auth (OAuth2 client credentials OR HMAC signing)  
* Rate limiting  
* WAF rules  
* API key management  
* Per-client policy model  
* Audit logs

Effort

* 3–5 weeks (1 backend \+ 0.5 DevOps)  
* Security review included

### RFQ Service (Quote lifecycle)

Scope

* Request validation  
* Ticket size enforcement  
* Hard-coded fee logic  
* Quote expiry (60 sec)  
* Idempotency  
* Storage \+ TTL

Effort

* 4–6 weeks (2 backend engineers)

Edge cases and concurrency handling matter here.

### 

### Execution \+ Trade Creation

Scope

* Atomic execution  
* Idempotent execute  
* Quote state transitions  
* Trade persistence  
  Error taxonomy

Effort

* 3–4 weeks (2 backend engineers)

This overlaps partially with RFQ work.

### QMS / Hedging Integration

You’re reusing existing logic — that’s good — but integration always takes longer than expected.

Scope

* Mapping schemas  
* Timeout \+ retry strategy  
* Hedge failure handling  
* Observability across regions (Africa ↔ Tokyo)

Effort

* 3–5 weeks (1–2 backend engineers)  
* Plus coordination with QMS team

### Trade Retrieval API \+ Storage

Scope

* Trade DB schema  
* Pagination  
* Query filters  
* Client reference lookup  
* Data retention policy

Effort

* 2–3 weeks (1 backend)

### Observability \+ Production Hardening

Scope

* Metrics (RFQ rate, expiry %, hedge latency)  
* Alerting  
* Correlation IDs  
* Load testing  
* Runbooks

Effort

* 2–4 weeks (shared between backend \+ DevOps)

This is usually underestimated.

# 

## Total Engineering Capacity Required

Minimal Team (Lean but realistic): 4.5 headcount

* 3 backend engineers  
* 1 Devops / Infra   
* 0.5 Architect / project manager

Timeline (3-3.5 months)

* Design & Security review 2 weeks  
* Core implementation 6-8 weeks  
* Internal integration & Testing 3-4 weeks  
* UAT \+ hardening 2 weeks

Burnrate $420,000

* Backend : 3 × 25,000 \= 75,000  
* DevOps: 20,000:  total Engineering Cost (4 Months)  
* PM: 10,000

### Monthly Infrastructure Costs (AWS)

* API Gateway: $2k–4k  
* Compute: $3k–6k  
* Database: $2k–4k  
* Logs \+ Monitoring: $1k–2k  
* Data transfer (cross-region): $1k–2k

Call 09/03/2026

Nkem Abuah  
Rofiat Abdulyekeen  
[Owenize Odia](mailto:oodia@blockchain.com)  
Michael Emeeka   
[Al Turnbull](mailto:al@blockchain.com)  
[Marc Sischka](mailto:msischka@blockchain.com)  
[Brian Cooper](mailto:bcooper@blockchain.com)  
[Swati Bhargava](mailto:sbhargava@blockchain.com)  
[Amaury Lamy](mailto:alamy@blockchain.com)

MarcS 

* List of supported coins: As many as you can get \- At least BTC   
  * Flutterwave will provide the list   
* Prefund/Credit:  
  * Want to do prefunding first and later credit   
* Trading hours  
  * 24/7 but not set on it   
* Settlement times  
  * Batching settlement on a master wallet  
* Required chain settlement support  
  * Chain supported: Polygon, base, solana  
  * Flutterwave to provide the list  
* Single wallet settlement or multi wallet  
* FW settlement process; single trade or batch  
* Reporting:   
  * Trade by trade? 

Amaury

* RFQ OnTheWireTime (how much time we need to keep the RFQ active) \- 60 sec  
* Confirm we will apply last look  
* Price provided is not inclusive of their spread \- not need  
* Projected volume of requests  
* Desired technical SLAs and budget errors  
* List of endpoints  
  * GET /rfq  
  * POST /execute\_rfq  
  * Get /trades  
  * Get /balance?  
  * I am pretty sure they will want a websocket for indicative pricing but brokerage uses CoinGecko to generate indicative prices. Indicative pricing needs to come from MRE but I would like to defer that build to later if we can \- not needed   
* Where are your gateways? 

Brian 

- Settlement frequency: once a day 

Action:

- Nkeem to share the list of coin and coin roadmap