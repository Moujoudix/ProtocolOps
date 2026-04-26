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

Open the Vite URL, usually `http://localhost:5173`.

## Environment

Secrets stay backend-only in `backend/.env`.

- `OPENAI_API_KEY`
- `SEMANTIC_SCHOLAR_API_KEY`
- `PROTOCOLS_IO_TOKEN`
- `TAVILY_API_KEY`

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
