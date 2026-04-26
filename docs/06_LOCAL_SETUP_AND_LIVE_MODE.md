# Local Setup and Live Mode

## Backend setup

Create the project venv once from the repository root:

```bash
python3 -m venv .venv
```

Install backend dependencies:

```bash
cd backend
cp .env.example .env
../.venv/bin/python -m pip install -e ".[dev]"
```

Run the backend on the default dev port:

```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

By default, Vite proxies `/api` and `/health` to `http://localhost:8000`.

## Presentation override on port 8002

When you run the backend on `8002`, also point the frontend proxy at that port:

```bash
cd backend
STRICT_LIVE_MODE=true EVIDENCE_MODE=strict_live ../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

```bash
cd frontend
VITE_BACKEND_TARGET=http://127.0.0.1:8002 npm run dev -- --host 127.0.0.1 --port 5175
```

## Environment variables

Key backend variables from `backend/.env.example`:

- `APP_ENV`
- `DATABASE_URL`
- `BACKEND_CORS_ALLOW_ORIGINS`
- `BACKEND_CORS_ALLOW_ORIGIN_REGEX`
- `OPENAI_API_KEY`
- `OPENAI_PARSE_MODEL`
- `OPENAI_PLAN_MODEL`
- `OPENAI_FALLBACK_MODEL`
- `EVIDENCE_MODE`
- `STRICT_LIVE_MODE`
- `CONSENSUS_MCP_ENABLED`
- `CONSENSUS_MCP_BRIDGE_URL`
- `CONSENSUS_MCP_SERVER_URL`
- `CONSENSUS_BRIDGE_HOST`
- `CONSENSUS_BRIDGE_PORT`
- `CONSENSUS_BRIDGE_HOME`
- `RUN_LIVE_INTEGRATION`
- `SEMANTIC_SCHOLAR_API_KEY`
- `PROTOCOLS_IO_TOKEN`
- `TAVILY_API_KEY`

Frontend development variables:

- `VITE_BACKEND_TARGET` for Vite proxy target
- `VITE_API_BASE_URL` only when you need an explicit API base instead of the proxy

## Consensus bridge startup

Start the local bridge from `backend/`:

```bash
cd backend
../.venv/bin/python -m consensus_bridge.main
```

Bridge endpoints:

- `GET http://127.0.0.1:8765/health`
- `POST http://127.0.0.1:8765/search`

The bridge root `/` returns `404` by design.

## Consensus OAuth flow

The bridge uses `mcp-remote` to connect to `https://mcp.consensus.app/mcp`.

Typical flow:

1. Start the bridge.
2. Trigger a real Consensus search by running Literature QC in the app or calling `/search`.
3. Complete the browser consent flow.
4. Confirm bridge health:

```bash
curl -sS http://127.0.0.1:8765/health
```

Expected success response:

```json
{
  "status": "ok",
  "authenticated": true,
  "detail": "Consensus OAuth cache detected"
}
```

If `CONSENSUS_BRIDGE_HOME` is set, the auth cache is kept under that local directory.

## Evidence modes

### `strict_live`

- real providers only
- no seeded fallback
- OpenAI failures and required evidence gaps become hard failures
- best mode for proving the workflow end to end

### `cached_live`

- replays a previously successful live-provider run from `EvidenceReplayCache`
- best mode for a stable demo after a live proof run has succeeded once

### `seeded_demo`

- deterministic fallback
- primarily supports local development and resilience when providers are missing or unstable

## Realized run outcomes

These are not configuration flags; they describe what happened:

- `fully_live`
- `degraded_live`
- `demo_fallback`

`degraded_live` means a run still used live providers, but at least one required provider partially failed.

## Readiness endpoint

Use readiness to check whether the current stack is demo-ready:

```bash
curl -sS http://127.0.0.1:8002/api/readiness
```

Key fields:

- `strict_live_mode`
- `evidence_mode`
- `live_ready`
- `cached_live_available`
- `seeded_demo_available`
- `providers[]`

The Consensus provider is only considered ready when the bridge is reachable **and** authenticated.

## Semantic Scholar HTTP 429 behavior

Semantic Scholar is used in public mode unless an API key is supplied.

If the public API rate-limits with HTTP `429`:

- Literature QC continues with other providers
- the run can still complete
- the realized run outcome becomes `degraded_live`
- the failure remains visible in `provider_trace`

This is what happened in the verified HeLa proof run.

## Local HeLa demo steps

Recommended hypothesis:

- `Main demo / HeLa cryopreservation`

Suggested flow:

1. Start bridge, backend, and frontend.
2. Open the frontend.
3. Choose the HeLa example from `Example hypotheses`.
4. Click `Run Literature QC`.
5. Inspect novelty signal, references, and search details.
6. Click `Generate Plan`.
7. Review `Overview`, `Materials`, `Sources`, and `Review`.
8. Use exports if needed.

## Troubleshooting

### Frontend shows no presets, system status, or recent runs

Cause: the Vite proxy is pointed at the wrong backend port.

Fix:

```bash
cd frontend
VITE_BACKEND_TARGET=http://127.0.0.1:8002 npm run dev -- --host 127.0.0.1 --port 5175
```

### `GET /` on the bridge says `Not Found`

Expected. The bridge is not a website. Use:

- `/health`
- `/search`

### `python` is unreliable in this shell

Use the project interpreter explicitly:

- `../.venv/bin/python`
- `../.venv/bin/pytest`

### Strict-live is enabled but runs still fail

Check:

- `OPENAI_API_KEY`
- `TAVILY_API_KEY`
- `PROTOCOLS_IO_TOKEN`
- `CONSENSUS_MCP_ENABLED=true`
- bridge health shows `authenticated: true`

