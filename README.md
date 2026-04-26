# ProtocolOps

AI Scientist MVP: an evidence-grounded experiment-planning web app that moves from hypothesis input to Literature QC to a review-ready experiment plan.

## Stack

- Backend: FastAPI, Pydantic, SQLModel, SQLite, httpx, OpenAI Python SDK
- Frontend: React, Vite, TypeScript, Tailwind, lucide-react
- External providers: Semantic Scholar, Europe PMC, protocols.io, OpenWetWare, Tavily, and supplier-domain search where keys are available

## Run Locally

Backend:

```bash
python3 -m venv .venv
cd backend
cp .env.example .env
../.venv/bin/python -m pip install -e ".[dev]"
../.venv/bin/uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`. In normal local development the frontend talks to the backend through the Vite proxy, so the browser stays on one visible origin.

## Environment

Secrets stay backend-only in `backend/.env`.

- `BACKEND_CORS_ALLOW_ORIGINS`
- `BACKEND_CORS_ALLOW_ORIGIN_REGEX`
- `OPENAI_API_KEY`
- `SEMANTIC_SCHOLAR_API_KEY`
- `PROTOCOLS_IO_TOKEN`
- `TAVILY_API_KEY`

Frontend runtime:

- `VITE_BACKEND_TARGET` configures the Vite dev proxy target and defaults to `http://localhost:8000`.
- `VITE_API_BASE_URL` is an optional override for unusual setups; normal local development should leave it unset.

## Local Dev

Start the backend on `http://localhost:8000` and the frontend on Vite. The frontend uses relative `/api` requests, and Vite proxies `/api` and `/health` to `VITE_BACKEND_TARGET`.

## Tunnel / Preview

For tunnel or deploy-preview access, keep the frontend using relative `/api` routes or set `VITE_API_BASE_URL` explicitly if the frontend and backend are on different origins. On the backend, allow those origins with `BACKEND_CORS_ALLOW_ORIGINS` and optionally `BACKEND_CORS_ALLOW_ORIGIN_REGEX` for dynamic preview hosts.

If provider keys are missing, the HeLa cryopreservation preset still works through deterministic seeded evidence. Other presets run through the same workflow with lower confidence and explicit evidence-gap warnings.

## Guardrails

- Literature QC is required before plan generation.
- Catalog numbers and prices remain `null` unless directly retrieved.
- Missing catalog or price sets `requires_procurement_check: true`.
- Protocol steps include `evidence_source_ids`, confidence, and expert-review flags.
- The app uses “not found in searched sources,” not claims that work has never been done.

## Tests

```bash
cd backend
pytest

cd ../frontend
npm test
```
