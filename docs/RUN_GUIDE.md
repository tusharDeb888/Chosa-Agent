# Alpha-Hunter — Run Guide

> Complete step-by-step instructions to run the Alpha-Hunter autonomous financial agent platform locally.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Quick Start (Docker Compose)](#2-quick-start-docker-compose)
3. [Local Development (Without Docker)](#3-local-development-without-docker)
4. [Configuration Reference](#4-configuration-reference)
5. [Running the Pipeline](#5-running-the-pipeline)
6. [API Endpoints](#6-api-endpoints)
7. [Frontend Dashboard](#7-frontend-dashboard)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Prerequisites

### Required
| Tool | Min Version | Check Command | Install |
|------|-------------|---------------|---------|
| **Docker** | 24+ | `docker --version` | [docker.com](https://docs.docker.com/get-docker/) |
| **Docker Compose** | v2 (built into Docker Desktop) | `docker compose version` | Comes with Docker Desktop |
| **Python** | 3.12+ | `python3 --version` | `brew install python@3.12` |
| **Node.js** | 20+ | `node --version` | `brew install node@20` |
| **Git** | Any | `git --version` | `brew install git` |

### Recommended
| Tool | Purpose |
|------|---------|
| **Groq API Key** | LLM-powered decision synthesis (free tier at [console.groq.com](https://console.groq.com)) |
| **Make** | Shortcut commands (pre-installed on macOS) |

> **Note:** The app runs fully without a Groq API key — it will automatically fall back to generating `WATCH` advisory decisions. For full BUY/SELL/HOLD recommendations, add your key.

---

## 2. Quick Start (Docker Compose)

This is the **recommended** way to run everything. Docker handles Postgres, Redis, backend, and frontend together.

### Step 1: Clone & Navigate

```bash
cd /Users/tushardeb/ET
```

### Step 2: Configure Environment

The `.env` file is already present. The only required edit is adding your Groq API key (optional):

```bash
# Open .env and set your Groq key (line 29)
# GROQ_API_KEY=gsk_your_key_here
```

To generate a fresh `.env` from the template:
```bash
cp .env.example .env
```

### Step 3: Start All Services

```bash
# Start Postgres, Redis, Backend, and Frontend
make up

# Or directly with docker compose:
docker compose up -d --build
```

This starts 4 containers:

| Container | Port | Description |
|-----------|------|-------------|
| `ah-postgres` | 5432 | PostgreSQL 16 + pgvector |
| `ah-redis` | 6379 | Redis 7 (AOF persistence) |
| `ah-backend` | 8000 | FastAPI + background workers |
| `ah-frontend` | 3000 | Next.js 15 dashboard |

### Step 4: Wait for Healthy Services

```bash
# Watch container status (all should show "healthy" or "running")
docker compose ps

# Follow logs to see startup progress
docker compose logs -f backend
```

Expected output:
```
ah-backend  | INFO  application_starting  app_name=Alpha-Hunter version=0.1.0
ah-backend  | INFO  redis_connected
ah-backend  | INFO  background_workers_started  count=4
```

### Step 5: Run Database Migrations

```bash
# Create all tables (users, portfolios, portfolio_positions, etc.)
docker compose exec backend alembic upgrade head

# If alembic has no migrations yet, generate the initial one:
docker compose exec backend alembic revision --autogenerate -m "initial"
docker compose exec backend alembic upgrade head
```

### Step 6: Seed Demo Data

```bash
docker compose exec backend python -m scripts.seed_mock_portfolio
```

Expected output:
```
✓ Created demo user: <uuid>
✓ Portfolio imported: 10 positions
  Total value: ₹12,97,000.00
  Cash balance: ₹5,00,000.00
✓ User agent state set to RUNNING
```

### Step 7: Start the Agent

The agent starts in `PAUSED` state by default. Activate it:

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/agent/lifecycle \
  -H "Content-Type: application/json" \
  -d '{"target_state": "RUNNING", "reason": "Initial startup"}'
```

Or use the **dashboard UI** at [http://localhost:3000](http://localhost:3000) → click the green **Start** button.

### Step 8: Open the Dashboard

Open your browser to:

| URL | Description |
|-----|-------------|
| **http://localhost:3000** | Command Center Dashboard |
| **http://localhost:8000/docs** | FastAPI Swagger UI (interactive API docs) |
| **http://localhost:8000/redoc** | ReDoc API documentation |
| **http://localhost:8000/api/v1/ops/health** | Health check endpoint |

---

## 3. Local Development (Without Docker)

For active backend development with hot-reload, run Postgres and Redis in Docker but the backend and frontend natively.

### Step 1: Start Infrastructure Only

```bash
# Start only Postgres + Redis (no backend/frontend containers)
docker compose up -d postgres redis
```

### Step 2: Set Up Python Environment

```bash
cd backend

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install all dependencies (production + dev)
pip install -e ".[dev]"
```

### Step 3: Configure Local Environment

The `.env` in the project root uses `localhost` URLs by default — correct for local dev:

```env
DATABASE_URL=postgresql+asyncpg://ahuser:ahpass@localhost:5432/alphahunter
DATABASE_URL_SYNC=postgresql://ahuser:ahpass@localhost:5432/alphahunter
REDIS_URL=redis://localhost:6379/0
```

### Step 4: Run Migrations & Seed

```bash
# Stay in backend/ directory
alembic revision --autogenerate -m "initial"
alembic upgrade head

# Seed demo portfolio
python -m scripts.seed_mock_portfolio
```

### Step 5: Start the Backend

```bash
# From backend/ directory
uvicorn app.main:app --reload --port 8000 --log-level info
```

The backend starts with **4 background workers** automatically:
- Ingestion Worker (market data → anomaly detection)
- Qualification Worker (signal validation)
- Orchestrator Worker (LangGraph pipeline)
- Notification Worker (WebSocket/SSE delivery)

### Step 6: Start the Frontend

```bash
# Open a new terminal
cd frontend

# Install dependencies (first time only)
npm install

# Start dev server
npm run dev
```

Frontend runs at [http://localhost:3000](http://localhost:3000).

---

## 4. Configuration Reference

### Critical Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GROQ_API_KEY` | *(empty)* | ⚡ Recommended | Groq API key for LLM synthesis. Without it, all decisions are WATCH. |
| `MARKET_PROVIDER` | `mock` | ✅ Set | `mock` for simulated data, `upstox` for live (Phase 2) |
| `DATABASE_URL` | localhost:5432 | ✅ Set | Async Postgres connection string |
| `REDIS_URL` | localhost:6379 | ✅ Set | Redis connection string |
| `AGENT_DEFAULT_STATE` | `PAUSED` | ✅ Set | Agent starts in this state on boot |
| `LOG_LEVEL` | `INFO` | Optional | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Agent Control Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_DEFAULT_STATE` | `PAUSED` | Initial state on startup |
| `CONTROL_CHANNEL` | `agent.control` | Redis Pub/Sub channel for state broadcasts |

### Policy Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `POLICY_MAX_POSITION_CONCENTRATION_PCT` | `25` | Max % of portfolio in one stock |
| `POLICY_MAX_DAILY_ACTIONS` | `20` | Max BUY/SELL recommendations per day |
| `POLICY_MIN_CONFIDENCE_BUY_SELL` | `60` | Minimum confidence to issue BUY/SELL |
| `POLICY_MAX_EVIDENCE_AGE_HOURS` | `24` | Max age of evidence in hours |

### Stream Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `STREAM_RETENTION_TICKS_MAXLEN` | `50000` | Max entries in market ticks stream |
| `STREAM_BATCH_SIZE` | `10` | Messages consumed per XREADGROUP call |
| `STREAM_BLOCK_MS` | `5000` | Block timeout for stream reads |

---

## 5. Running the Pipeline

### Pipeline Flow

```
Market Ticks → Anomaly Detection → Signal Candidate → Qualification
→ Qualified Signal → [Fan-out per user] → LangGraph Pipeline:
    Enrich → Synthesize (Groq LLM) → Policy Check → Publish
→ WebSocket/SSE → Dashboard
```

### Verify the Pipeline is Working

```bash
# 1. Check agent status
curl http://localhost:8000/api/v1/agent/status | python3 -m json.tool

# 2. Check operational metrics
curl http://localhost:8000/api/v1/ops/metrics | python3 -m json.tool

# 3. Check health
curl http://localhost:8000/api/v1/ops/health | python3 -m json.tool
```

### Expected Metrics After ~30 Seconds

```json
{
  "streams": {
    "market.ticks.raw": 0,
    "signals.candidate": 15,
    "signals.qualified": 3,
    "agent.decisions": 2,
    "alerts.user_feed": 2
  },
  "dlq": {},
  "agent_state": "RUNNING"
}
```

### Agent State Control

```bash
# Pause the agent (stops processing, in-flight completes)
curl -X POST http://localhost:8000/api/v1/agent/lifecycle \
  -H "Content-Type: application/json" \
  -d '{"target_state": "PAUSED", "reason": "Maintenance"}'

# Resume
curl -X POST http://localhost:8000/api/v1/agent/lifecycle \
  -H "Content-Type: application/json" \
  -d '{"target_state": "RUNNING", "reason": "Resuming operations"}'

# Emergency kill (stops ALL processing in <500ms)
curl -X POST http://localhost:8000/api/v1/agent/lifecycle \
  -H "Content-Type: application/json" \
  -d '{"target_state": "TERMINATED", "reason": "Emergency stop"}'
```

### Import a Custom Portfolio

```bash
curl -X POST http://localhost:8000/api/v1/portfolio/mock \
  -H "Content-Type: application/json" \
  -d '{
    "user_email": "demo@alphahunter.ai",
    "cash_balance": 500000,
    "holdings": [
      {"symbol": "RELIANCE", "quantity": 50, "avg_price": 2450, "sector": "Oil & Gas"},
      {"symbol": "TCS", "quantity": 25, "avg_price": 3800, "sector": "IT"},
      {"symbol": "INFY", "quantity": 100, "avg_price": 1550, "sector": "IT"}
    ]
  }'
```

---

## 6. API Endpoints

### Agent Control
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/agent/lifecycle` | Change agent state (RUNNING/PAUSED/TERMINATED) |
| `GET` | `/api/v1/agent/status` | Current state + worker heartbeats |

### Portfolio
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/portfolio/mock` | Import mock portfolio from JSON |
| `GET` | `/api/v1/portfolio/{user_id}` | Get portfolio for a user |

### Real-Time Alerts
| Method | Endpoint | Description |
|--------|----------|-------------|
| `WS` | `/api/v1/alerts/ws?user_id=all` | WebSocket stream (all alerts) |
| `GET` | `/api/v1/alerts/stream?user_id=all` | SSE stream (fallback) |

### Operations
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/ops/health` | Health check (Postgres + Redis) |
| `GET` | `/api/v1/ops/metrics` | Stream lengths, DLQ depths, worker status |

### Documentation
| URL | Description |
|-----|-------------|
| `http://localhost:8000/docs` | Swagger UI (interactive) |
| `http://localhost:8000/redoc` | ReDoc (reference) |

---

## 7. Frontend Dashboard

### Features

| Panel | What It Shows |
|-------|---------------|
| **KPI Cards** | Ticks processed, stream events, alerts, DLQ depth, agent state |
| **Live Alert Feed** | Real-time decisions via WebSocket with ticker, action (BUY/SELL/WATCH), confidence %, rationale |
| **Stream Pipeline** | Per-topic event counts with progress bars |
| **Worker Status** | Health indicators for ingestion, qualification, orchestrator, notifications |
| **State History** | Recent agent state transitions |
| **Control Deck** | Start / Pause / Kill buttons in the header |

### WebSocket Test (Browser Console)

```javascript
const ws = new WebSocket("ws://localhost:8000/api/v1/alerts/ws?user_id=all");
ws.onmessage = (e) => console.log("Alert:", JSON.parse(e.data));
ws.onopen = () => console.log("Connected to Alpha-Hunter");
```

---

## 8. Troubleshooting

### Container Won't Start

```bash
# Check container status
docker compose ps

# Check specific container logs
docker compose logs backend
docker compose logs postgres

# Rebuild from scratch
docker compose down -v
docker compose up -d --build
```

### `alembic upgrade head` Fails

```bash
# If no migration scripts exist yet, generate one first:
cd backend
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

If you get a connection error, ensure Postgres is running:
```bash
docker compose ps postgres
# Should show "healthy"
```

For local dev (not Docker), verify your `DATABASE_URL_SYNC` in `.env` points to `localhost:5432`.

### Seed Script Fails

```bash
# Ensure you're in the backend directory and migrations are applied
cd backend
python -m scripts.seed_mock_portfolio
```

Common error: `relation "users" does not exist` → run migrations first.

### Frontend Can't Reach Backend

1. **CORS**: The backend allows all origins (`*`) in dev mode — this should work.
2. **Port mismatch**: Verify `.env` has:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   NEXT_PUBLIC_WS_URL=ws://localhost:8000
   ```
3. **Docker networking**: If running frontend in Docker and backend in Docker, they communicate via container names. If running frontend locally but backend in Docker, use `localhost:8000`.

### No Alerts Appearing

1. Check agent is `RUNNING`:
   ```bash
   curl http://localhost:8000/api/v1/agent/status
   ```
2. If state is `PAUSED`, start it:
   ```bash
   curl -X POST http://localhost:8000/api/v1/agent/lifecycle \
     -H "Content-Type: application/json" \
     -d '{"target_state": "RUNNING", "reason": "Start"}'
   ```
3. Check backend logs for anomaly detection:
   ```bash
   docker compose logs -f backend | grep "anomalies_detected"
   ```
4. The mock provider generates anomalies at ~3% probability per tick. It may take 10-30 seconds before the first qualified signal.

### Groq LLM Errors

Without `GROQ_API_KEY`, the system automatically falls back to `WATCH` decisions. This is expected behavior per PRD:
```
"Automated WATCH advisory for RELIANCE. LLM synthesis unavailable."
```

To enable full synthesis:
1. Get a free key at [console.groq.com](https://console.groq.com)
2. Add to `.env`: `GROQ_API_KEY=gsk_your_key_here`
3. Restart backend: `docker compose restart backend`

### Port Conflicts

If ports 5432, 6379, 8000, or 3000 are already in use:

```bash
# Check what's using a port
lsof -i :8000

# Change ports in .env
POSTGRES_PORT=5433
REDIS_PORT=6380
BACKEND_PORT=8001
FRONTEND_PORT=3001
```

Then restart: `docker compose down && docker compose up -d`

---

## Makefile Commands Reference

```bash
make help              # Show all commands
make up                # Start all services
make down              # Stop all services
make down-clean        # Stop + delete all data
make logs              # Tail all logs
make logs-backend      # Tail backend logs only
make migrate           # Run database migrations
make migrate-create    # Create new migration (MSG="description")
make seed              # Seed demo portfolio
make test              # Run all tests
make clean             # Remove __pycache__ and .pyc files
```
