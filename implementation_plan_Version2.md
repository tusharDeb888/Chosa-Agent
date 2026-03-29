# Alpha-Hunter — Enterprise Implementation Plan (v2)

## Overview

Alpha-Hunter is a **continuously running autonomous financial agent platform** that ingests real-time market streams, detects anomalies, performs autonomous evidence gathering, and produces portfolio-personalized recommendations with explainability and human control boundaries.

This plan covers implementation from an empty workspace to a production-ready **Phase 1 MVP**, with explicit reliability controls for continuous runtime and extension points for Phases 2–4.

---

## Finalized Phase-1 Decisions (Locked)

1. **Market Data Source**: Start with **mock market data generator** in Phase 1, with Upstox adapter behind provider interface.
2. **LLM Strategy**: **Groq primary** with mandatory fallback behavior (`WATCH` advisory when unavailable).
3. **Tenancy Mode**: **Single-tenant runtime in Phase 1**, but tenant-aware schema from day one (`tenant_id` columns).
4. **Embeddings**: **Local embeddings** (sentence-transformers) for Phase 1.
5. **Deployment Target**: Docker Compose for local/dev.
6. **Frontend**: Next.js 15 Command Center as primary UI.

---

## Non-Negotiable Runtime Invariants

1. No `RUNNING` state -> no autonomous pipeline execution.
2. No valid schema -> no recommendation publish.
3. No policy pass -> no actionable recommendation.
4. No checkpoint write -> no node completion ack.
5. No tenant isolation guarantees -> fail closed.
6. Kill switch must block new work in **<500ms**.

---

## Canonical Agent State Contract (Unified Everywhere)

Use exactly one enum in DB + backend + frontend + workers:

- `RUNNING`
- `PAUSED`
- `TERMINATED`
- `DEGRADED`

> `STOPPED`, `ACTIVE`, or any alternate state names are disallowed.

---

## Technology Stack

| Layer | Technology | Rationale |
|:------|:-----------|:----------|
| **Runtime** | Python 3.12+ | Async-native, LangGraph ecosystem |
| **API Framework** | FastAPI + Uvicorn | Async, OpenAPI, WS support |
| **Agent Orchestrator** | LangGraph 0.3+ | Stateful graph execution |
| **Checkpointing** | langgraph-checkpoint-postgres | Durable workflow resume |
| **Event Backbone** | Redis Streams | Durable queueing, consumer groups, replay |
| **Control Broadcast** | Redis Pub/Sub | Sub-500ms kill switch propagation |
| **Cache** | Redis 7+ | Shared runtime state/rate limiting |
| **Database** | PostgreSQL 16 + pgvector | ACID, vector search, JSONB |
| **LLM Provider** | Groq + Instructor | Structured low-latency outputs |
| **Web Scraping** | Crawl4AI | Async evidence extraction |
| **Market Provider** | Mock provider + Upstox adapter | Decoupled ingestion interface |
| **Frontend** | Next.js 15 App Router | Real-time command center |
| **Observability** | OpenTelemetry + Prometheus | Tracing, metrics, SLOs |
| **Containerization** | Docker + Docker Compose | Reproducible local/dev |

---

## Repository Structure

```text
/Users/tushardeb/ET/
├── docker-compose.yml
├── .env.example
├── Makefile
├── README.md
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── core/
│   │   ├── db/
│   │   ├── streams/
│   │   ├── ingestion/
│   │   ├── qualification/
│   │   ├── orchestrator/
│   │   ├── enrichment/
│   │   ├── decision/
│   │   ├── policy/
│   │   ├── portfolio/
│   │   ├── notifications/
│   │   ├── control/
│   │   └── api/v1/
│   ├── tests/
│   ├── scripts/
│   └── Dockerfile
│
├── frontend/
│   ├── package.json
│   ├── src/app/{control,feed,portfolio,ops}
│   └── Dockerfile
│
├── proto/upstox/MarketDataFeed.proto
└── docs/{architecture.md,api-contracts.md,runbook.md}
```

---

## Phase 1 Scope (MVP Agent Runtime)

Pipeline: **Ingestion -> Qualification -> Orchestration -> Enrichment -> Synthesis -> Policy -> Delivery -> Control**

Includes:
- Continuous workers
- Kill switch
- Strict schema validation
- Idempotency + dedupe
- Durable checkpoints
- SSE/WS delivery
- Core dashboard panels

---

## Component-by-Component Implementation

### 1) Foundation & Infra

#### [NEW] `docker-compose.yml`
Services:
- `postgres` (with pgvector)
- `redis`
- `backend`
- `frontend`
- optional `prometheus` + `grafana` (dev profile)

#### [NEW] `.env.example`
Add required groups:
- `DB_*`
- `REDIS_*`
- `GROQ_*`
- `MARKET_PROVIDER=mock|upstox`
- `CONTROL_CHANNEL=agent.control`
- `STREAM_RETENTION_*`
- `IDEMPOTENCY_TTL_SECONDS`
- `SLO_*`

#### [NEW] `Makefile`
Targets:
- `make up/down/logs`
- `make migrate`
- `make seed`
- `make test-unit`
- `make test-integration`
- `make test-e2e`
- `make replay-dlq`

---

### 2) Core Kernel

#### [NEW] `app/core/enums.py`
- `AgentState`: RUNNING, PAUSED, TERMINATED, DEGRADED
- `Decision`: BUY, SELL, HOLD, WATCH
- `PortfolioMode`: MOCK_JSON, UPSTOX_LIVE
- `StreamTopic` constants

#### [NEW] `app/core/schemas.py`
- Signal, evidence, decision, guarded decision, canonical portfolio models
- Strict typed contracts shared across modules

#### [NEW] `app/core/events.py`
- Event envelope + idempotency key:
  `hash(source + ticker + event_ts + anomaly_type)`
- Serialization contract for streams/pubsub

#### [NEW] `app/core/observability.py`
- OTel setup + structured logs
- Required keys: `trace_id, workflow_id, signal_id, user_id, tenant_id, ticker, agent_state`

#### [NEW] `app/core/security.py`
- Secret redaction filter for logs
- Envelope encryption helpers (KMS-ready interface)

---

### 3) Database Layer

#### [NEW] `app/db/models.py`
Tables:
- `users` (includes `tenant_id`, `agent_state`)
- `portfolios`
- `portfolio_positions` (projection table)
- `agent_execution_logs`
- `market_knowledge_base`
- `processed_events` (**new**, idempotency store)
- LangGraph checkpoint tables (official schema)

Indexes:
- `portfolio_positions(symbol)`
- `portfolio_positions(user_id, symbol)`
- partial index on active users
- unique index on `processed_events(idempotency_key)`

#### [NEW] Alembic migrations
- Enable pgvector
- Add tables/indexes
- Add tenant columns now (single-tenant runtime still)
- Use official langgraph checkpoint migration/bootstrap path

---

### 4) Redis Streams + Control Plane Broadcast

#### [NEW] `app/streams/producer.py`
- XADD wrapper with per-topic retention policy

#### [NEW] `app/streams/consumer.py`
- XREADGROUP, XACK, XAUTOCLAIM
- Retry with bounded attempts

#### [NEW] `app/streams/dlq.py`
- Dead-letter routing on max retries

#### Stream Retention Policy (explicit)
- High volume (`market.ticks.raw`, `signals.candidate`): `MAXLEN ~` bounded
- Critical replay (`signals.qualified`, `agent.decisions`, `alerts.user_feed`): longer retention window
- DLQ: no aggressive trim

#### Control Channel
- Redis Pub/Sub topic: `agent.control`
- Used for immediate state propagation (kill switch)
- Worker local cache updates instantly; polling remains fallback heartbeat

---

### 5) Ingestion Service

#### [NEW] `app/ingestion/providers/base.py`
- Interface:
  - `connect()`
  - `subscribe(symbols)`
  - `stream_ticks()`
  - `close()`

#### [NEW] `app/ingestion/providers/mock.py`
- Realistic stochastic tick generation (volume, spread, bursts)

#### [NEW] `app/ingestion/providers/upstox.py`
- Upstox adapter implementation (kept optional in Phase 1)

#### [NEW] `app/ingestion/worker.py`
- Always-on loop
- Auto-restart with bounded retries + jitter
- Emits heartbeat every 5s

---

### 6) Signal Qualification Service

#### [NEW] `app/qualification/service.py`
Applies all criteria:
1. freshness
2. liquidity
3. statistical breach
4. confidence floor
5. system/agent state gate

Outputs:
- `QualifiedSignal` OR `RejectedSignal(reason_code)`

---

### 7) Orchestrator (LangGraph)

#### [NEW] `app/orchestrator/graph.py`
Graph:
`START -> enrich -> synthesize -> policy_check -> publish -> END`
with downgrade path to `WATCH` on policy violations.

#### [NEW] `app/orchestrator/worker.py`
- Consumes `signals.qualified`
- Fan-out using `portfolio_positions`
- Per-user execution id:
  `hash(user_id + signal_id + workflow_version)`

#### Checkpointing Rule
- Node completion is acknowledged only after checkpoint persistence succeeds.

---

### 8) Enrichment Service

#### [NEW] `app/enrichment/scraper.py`
- Allowlist-only domains
- Concurrency caps
- Freshness tagging

#### [NEW] `app/enrichment/retriever.py`
- pgvector retrieval with recency weighting

#### Failure Fallback
- If crawl fails, fallback to vector-only context and set `degraded_context=true`.

---

### 9) Decision Engine

#### [NEW] `app/decision/engine.py`
- Groq + Instructor structured output
- Strict schema parse and validation

#### Fallback Behavior (mandatory in Phase 1)
If LLM unavailable/timeouts/circuit open:
- Emit valid fallback decision:
  - `decision=WATCH`
  - `confidence` capped low
  - `risk_flags += ["LLM_UNAVAILABLE"]`
  - include rationale and ttl
- Pipeline continues; no hard failure

---

### 10) Policy Guardrail

#### [NEW] `app/policy/engine.py`
Rules:
- max position concentration
- max daily actionable recs
- min confidence for BUY/SELL
- max evidence age

Violations:
- downgrade to WATCH
- append `policy_reason_codes`

---

### 11) Portfolio Service

#### [NEW] `app/portfolio/service.py`
Modes:
- MOCK_JSON
- UPSTOX_LIVE

#### Atomic Consistency Rule (critical)
Any portfolio write must update:
- `portfolios`
- `portfolio_positions`
in **one transaction**.

If transaction fails, rollback all changes.

---

### 12) Notifications

#### [NEW] `app/notifications/service.py`
- At-least-once delivery
- Dedup by decision/event id

#### [NEW] WS + SSE endpoints
- WS primary
- SSE fallback

---

### 13) Control Plane & Kill Switch

#### [NEW] `app/control/router.py`
- lifecycle/status endpoints
- authenticated + authorized operations only

#### [NEW] `app/control/kill_switch.py`
- Writes canonical agent state to DB + Redis cache
- Broadcasts state event on `agent.control` pub/sub
- Workers update local state immediately on broadcast
- Fallback polling every short interval

---

### 14) API Contracts (Phase 1)

- `POST /api/v1/agent/lifecycle`
- `GET /api/v1/agent/status`
- `POST /api/v1/portfolio/mock`
- `POST /api/v1/portfolio/sync/upstox` (stub allowed)
- `GET /api/v1/alerts/stream`
- `WS /api/v1/alerts/ws`
- `GET /api/v1/ops/health`
- `GET /api/v1/ops/metrics`

---

### 15) Frontend (Next.js 15 Command Center)

Pages:
- `/control` (activate/pause/terminate + kill switch)
- `/feed` (live recommendations + citations + freshness)
- `/portfolio` (mock upload + sync status)
- `/ops` (worker health, lag, DLQ depth)

Mandatory UX states:
1. Global banner if `PAUSED` or `TERMINATED`
2. Decision badge for `DEGRADED_CONTEXT`
3. Visible connection health indicators

---

## Backpressure, Rate Limit, and Circuit Breakers

### Concurrency Controls
- Max orchestration tasks per worker (configurable)
- Global semaphore for LLM calls

### Rate Budgeting
- Per-minute LLM token/request budget
- Queue when budget exceeded

### Circuit Breakers
- Open on sustained failures (configurable threshold)
- Half-open probe window
- Auto-recover or remain open

---

## SLO Contract (Phase 1)

Latency measured from:
- **Start**: event accepted from `signals.qualified`
- **End**: alert successfully enqueued for WS/SSE delivery

Targets:
- p50 < 1.2s
- p95 < 3.0s
- p99 < 5.0s

On sustained p95 breach:
- mark runtime `DEGRADED`
- emit ops alert event

---

## Security Baseline (Phase 1)

- Secrets never exposed to frontend
- Secret redaction in logs
- Encrypted token storage
- AuthN/AuthZ required for control routes
- Audit log for lifecycle changes and decisions
- Key rotation playbook stub included in docs

---

## Verification Plan

### Automated

```bash
make test-unit
make test-integration
make test-e2e
make replay-dlq
```

Required tests:
- kill switch propagation <500ms
- malformed LLM output rejected
- duplicate signals deduped via processed_events
- crash mid-node resumes from checkpoint
- fallback WATCH on LLM outage
- portfolio + projection atomic update test

### Manual

- Run dashboard and validate all 4 panels
- lifecycle transitions RUNNING->PAUSED->RUNNING->TERMINATED
- simulate degraded enrichment and LLM outage
- verify alerts still published with correct degraded markers

---

## Acceptance Criteria (Phase 1 Gate)

1. Continuous run for 24h in dev soak without manual restart.
2. Kill switch blocks new tasks in <500ms (p95).
3. No duplicate decisions for duplicate events.
4. Resume from checkpoint after forced crash.
5. All published recommendations are schema-valid.
6. Fallback WATCH published when LLM unavailable.
7. No secrets present in logs or client payloads.

---

## Phase 2–4 Extension Path

### Phase 2 (Reliability/Scale)
- 7-day soak
- advanced replay/DLQ ops
- horizontal autoscaling
- stricter SLO alerting

### Phase 3 (Compliance)
- full RLS enablement
- key rotation automation
- audit export workflows

### Phase 4 (Execution Intelligence)
- broker order orchestration
- approval workflows
- execution tracking and reconciliation