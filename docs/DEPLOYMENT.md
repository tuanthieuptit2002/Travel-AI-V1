# Production deployment

This guide covers hardening TripMind AI for production: secrets, Docker, auth, observability, and operational checks.

## Architecture (production)

```text
Client (Next.js)
    │  HTTPS + Bearer guest/user JWT
    ▼
API (FastAPI / Uvicorn)
    │  request_id → rate limit → authz
    │
    ├─ LangGraph multi-agent (iteration + timeout + tool-call caps)
    │     └─ typed tools → providers (timeout + retry)
    │
    ├─ PostgreSQL + pool
    ├─ Redis (cache + rate limit)
    └─ optional Sentry
```

Observability chain:

`request → agent → node → tool → external API → LLM → response`

Logs are structured (JSON in production) and redact API keys, tokens, and passwords.

## Prerequisites

- Docker + Docker Compose
- Strong secrets for `SECRET_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `API_KEYS`
- TLS terminator (Cloudflare / nginx / Traefik) in front of API and web

## Configure secrets

```bash
cp .env.production.example .env.production
# edit .env.production — never commit real values
```

Required production settings:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | JWT signing (≥32 chars, unique) |
| `AUTH_ENABLED=true` | Require Bearer / API key |
| `API_KEYS` | Service credentials |
| `CORS_ORIGINS` | Explicit frontend origins |
| `TRUSTED_HOSTS` | Host allowlist |
| `DATABASE_URL` / `REDIS_URL` | Infra |
| `SENTRY_DSN` | Optional error tracking |

Production startup **refuses** weak `SECRET_KEY` values and empty `API_KEYS` when auth is enabled.

## Deploy with Docker

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

Services:

- `postgres` — not published to the host
- `redis` — password-protected, not published
- `api` — FastAPI on `${API_PORT:-8000}`
- `web` — Next.js standalone on `${WEB_PORT:-3000}`

Health:

- Liveness: `GET /health`, `GET /api/v1/health`
- Readiness: `GET /api/v1/ready` (DB + Redis)

## Authentication & authorization

1. Frontend calls `POST /api/v1/auth/guest` with the guest UUID → JWT
2. Subsequent calls send `Authorization: Bearer <token>`
3. Service automations may use `X-API-Key`
4. Memory and trip access is scoped to the authenticated `user_id` (service/admin roles bypass)

Local development keeps `AUTH_ENABLED=false` so existing scripts keep working.

## Security controls

- No API keys in frontend (`NEXT_PUBLIC_*` is public-only)
- Never trust LLM-generated URLs (`is_safe_external_url`)
- No arbitrary SQL / shell tools; tools use Pydantic schemas + `run_safely`
- Prompt-injection phrases filtered before the agent runs
- Agent: max iterations, wall-clock timeout, max tool calls
- Provider HTTP: timeout, retries, exponential backoff
- LLM/embeddings: timeout + retries + token/cost tracking
- Rate limits on all routes (stricter on `/trips/plan`)
- Redis cache for weather responses
- SQLAlchemy connection pooling (`pool_pre_ping`, size/overflow/recycle)
- OpenAPI docs disabled when `APP_ENV=production`

## What is never logged

- API keys / access tokens / passwords
- `Authorization` / `X-API-Key` header values
- Raw provider error bodies that may contain secrets

## Rollback

```bash
docker compose -f docker-compose.prod.yml down
# restore previous image tags / .env.production backup
```

## Post-deploy checklist

- [ ] `/api/v1/ready` returns `ok`
- [ ] Guest token + plan trip works end-to-end
- [ ] Unauthorized access to another user's `/memory/{id}` returns 403
- [ ] Rate limit returns 429 under burst traffic
- [ ] Secrets are not present in frontend bundle / browser network logs
- [ ] Sentry (if configured) receives a test exception without PII
