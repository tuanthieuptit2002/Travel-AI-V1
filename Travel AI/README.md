# TripMind AI

TripMind AI is a production-oriented, agentic travel planner focused on Vietnam. The stack includes a Next.js frontend, FastAPI backend, PostgreSQL/pgvector, Redis, curated Vietnam place suggestions, Open-Meteo weather, and a LangGraph multi-agent travel planner. Google Maps opens from direct links in the frontend and requires no API key. Flight booking is not integrated yet.

## Architecture

```text
Frontend (Next.js)
      │  Bearer JWT (guest) / public API URL only
      ▼
API (FastAPI)
  middleware: request ID → rate limit → CORS → authz
      │
      ├─ Auth (/auth/guest, JWT, API keys)
      ├─ Trips (/trips/plan + CRUD)
      ├─ Memory (user preferences)
      └─ Health (/health, /ready)
            │
            ▼
      LangGraph Supervisor
        Flight / Hotel / Place / Weather / Itinerary / Budget / Validation
            │
            ├─ Typed tools (validated args, no shell/SQL)
            ├─ Providers (timeout + retry)
            ├─ Redis cache + rate limit
            └─ PostgreSQL pool
```

Observability path: **request → agent → node → tool → external API → LLM → response**.

Secrets stay server-side only. Frontend may only use `NEXT_PUBLIC_*` values.

## Environment variables

See `backend/.env.example`, root `.env.example`, and `.env.production.example`.

| Area | Key variables |
|------|----------------|
| Core | `APP_ENV`, `SECRET_KEY`, `CORS_ORIGINS`, `TRUSTED_HOSTS` |
| Auth | `AUTH_ENABLED`, `API_KEYS`, `JWT_*` |
| Data | `DATABASE_URL`, `REDIS_URL`, `DB_POOL_*` |
| Providers | `TRAVEL_DATA_MODE`, `OPEN_METEO_*`, `PROVIDER_HTTP_*` |
| LLM | `OPENAI_API_KEY`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` |
| Agent | `AGENT_MAX_ITERATIONS`, `AGENT_TIMEOUT_SECONDS`, `AGENT_MAX_TOOL_CALLS` |
| Ops | `RATE_LIMIT_*`, `CACHE_*`, `LOG_JSON`, `SENTRY_DSN` |

Never put `OPENAI_API_KEY`, `SECRET_KEY`, or `API_KEYS` in `NEXT_PUBLIC_*`.

## Local development

1. Copy env files and set local passwords:

   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   ```

2. Start Postgres + Redis:

   ```bash
   docker compose up -d
   ```

3. Backend:

   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```

4. Frontend:

   ```bash
   cd frontend
   npm install
   cp .env.example .env.local
   npm run dev
   ```

Frontend: http://localhost:3000 · API docs (non-prod): http://localhost:8000/docs

### Migrations

```bash
cd backend && source .venv/bin/activate
alembic upgrade head
```

## Agent tool layer

`app.tools.create_agent_tools()` builds typed LangChain tools. Agents never receive raw SDKs, DB sessions, or shell access. Tool args are Pydantic-validated; failures become generic structured errors via `run_safely`.

## LangGraph multi-agent

Supervisor + specialists on shared `MultiAgentState`. Details: `backend/app/agent/multi/AGENTS.md`.

Guards (env-tunable): max iterations, timeout, repair attempts, max tool calls, per-agent error recovery, fallback finalize.

## Testing

```bash
cd backend
source .venv/bin/activate
pytest
```

```bash
cd frontend
npm run build
```

## Evaluation

Offline mock-provider evaluation for five destinations. See `backend/evaluation/README.md`.

```bash
cd backend && source .venv/bin/activate
python scripts/run_evaluation.py
python scripts/run_evaluation.py --save-baseline
pytest tests/test_evaluation_regression.py -q
```

## Docker deployment

Production compose + runbook: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

```bash
cp .env.production.example .env.production
# fill secrets
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Local infra-only compose remains `docker-compose.yml` (Postgres + Redis for developers).

## Security considerations

- **AuthN/AuthZ:** JWT guest tokens + optional API keys; ownership checks on memory/trips when `AUTH_ENABLED=true`
- **Rate limiting:** Redis sliding window with in-memory fallback; stricter budget on `/trips/plan`
- **Caching:** Redis (or memory fallback) for weather
- **Prompt injection:** user text sanitized before the agent
- **URL safety:** LLM/tool URLs must pass HTTPS + host allow/deny checks (no localhost/metadata IPs)
- **SQL safety:** SQLAlchemy only; no agent-facing raw SQL
- **No shell tools:** explicitly forbidden in the tool factory
- **Secrets:** production validator rejects weak `SECRET_KEY`; docs disabled in production
- **Logging:** JSON logs with redaction; no API keys/tokens/passwords
- **Timeouts/retries:** providers + LLM/embeddings; agent wall-clock + iteration caps
- **Cost tracking:** token/USD estimates attached to the request cost tracker

## API (v1)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/auth/guest` | Issue guest JWT |
| `GET` | `/api/v1/auth/me` | Current principal |
| `POST` | `/api/v1/trips/plan` | Run travel agent |
| `POST` | `/api/v1/trips` | Create trip |
| `GET` | `/api/v1/trips` | List trips |
| `GET` | `/api/v1/trips/{trip_id}` | Get trip |
| `GET/POST/DELETE` | `/api/v1/memory/{user_id}` | Preferences |
| `GET` | `/api/v1/health` | Liveness |
| `GET` | `/api/v1/ready` | Readiness (DB/Redis) |

## Remaining work

- Persist trips/memory/RAG to PostgreSQL in the live API path (repos already exist)
- Full user signup/login beyond guest JWT
- Amadeus flight/hotel live providers behind existing interfaces
