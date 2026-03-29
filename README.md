# Alpha-Hunter

**Autonomous Financial Agent Platform** — Continuously running agent that ingests real-time market streams, detects anomalies, performs autonomous evidence gathering, and produces portfolio-personalized recommendations with explainability and human control boundaries.

## Architecture

```
Market Stream → Ingestion → Qualification → Orchestrator (LangGraph)
                                                ├── Enrichment (Crawl4AI + pgvector)
                                                ├── Synthesis (Groq LLM)
                                                ├── Policy Guardrail
                                                └── Notification (WS/SSE) → Command Center
```

## Quick Start

```bash
# 1. Copy environment template
cp .env.example .env
# Edit .env with your GROQ_API_KEY and other secrets

# 2. Start all services
make up

# 3. Run database migrations
make migrate

# 4. Seed mock portfolio data
make seed

# 5. Open Command Center
open http://localhost:3000
```

## Agent States

| State | Behavior |
|:------|:---------|
| `RUNNING` | Full pipeline execution |
| `PAUSED` | No new work; in-flight completes |
| `TERMINATED` | Hard stop; requires re-init |
| `DEGRADED` | Reduced capability mode |

## API Endpoints

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| POST | `/api/v1/agent/lifecycle` | Change agent state |
| GET | `/api/v1/agent/status` | Current state + metrics |
| POST | `/api/v1/portfolio/mock` | Upload mock portfolio |
| POST | `/api/v1/portfolio/sync/upstox` | Sync from Upstox |
| GET | `/api/v1/alerts/stream` | SSE alert stream |
| WS | `/api/v1/alerts/ws` | WebSocket alerts |
| GET | `/api/v1/ops/health` | Health check |
| GET | `/api/v1/ops/metrics` | Prometheus metrics |

## Development

```bash
make help          # Show all available commands
make logs          # Tail all service logs
make test          # Run all tests
make migrate       # Run DB migrations
```

## Tech Stack

- **Backend**: Python 3.12 / FastAPI / LangGraph / Redis Streams / PostgreSQL + pgvector
- **Frontend**: Next.js 15 / TypeScript / TanStack Query
- **LLM**: Groq (structured output via Instructor)
- **Scraping**: Crawl4AI
- **Observability**: OpenTelemetry + Prometheus
# Chosa-Agent
