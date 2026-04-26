# ProtocolOps

AI Scientist MVP+: an evidence-grounded experiment-planning web app that moves from hypothesis input to Literature QC to a review-ready experiment plan.

The internal source flow is documented in [RESOURCE_ROUTING.md](RESOURCE_ROUTING.md). The app now follows one fixed pipeline:

1. hypothesis input
2. OpenAI structured parse
3. Literature QC
4. Evidence Pack construction
5. OpenAI structured experiment-plan generation
6. frontend rendering with sources, confidence, and review flags

## Demo Videos

- [Demo video: ProtocolOps user workflow](docs/videos/demo.mp4)
- [Technical video: architecture and implementation](docs/videos/tech.mp4)

The demo video shows the HeLa cryopreservation workflow: hypothesis input, Literature QC, EvidencePack-backed plan generation, materials/procurement checks, sources, and review/export actions.

The technical video explains the FastAPI + React architecture, Consensus-first Literature QC, provider routing, OpenAI structured outputs, Pydantic guardrails, and strict-live/cached-live evidence modes.

## Product Features

The app now includes:

- provider readiness checks for OpenAI, Consensus, Tavily, protocols.io, and Semantic Scholar public mode
- explicit evidence modes for strict live, cached live, and seeded demo runs
- persistent run history with reopenable public runs
- stage event timelines per run
- structured scientist review capture
- retrieval-memory guidance from prior reviewed runs
- export surfaces for JSON, citations, and procurement follow-up
- section-level quality metrics for literature, protocol, materials, budget, and operational readiness

## Stack

- Backend: FastAPI, Pydantic, SQLModel, SQLite, httpx, OpenAI Python SDK
- Frontend: React, Vite, TypeScript, Tailwind, lucide-react
- External providers: Consensus MCP, Semantic Scholar, Europe PMC, NCBI E-utilities, arXiv, protocols.io, OpenWetWare, Tavily, and supplier-domain search where keys are available

## Run Locally

Backend:

```bash
python3 -m venv .venv
cd backend
cp .env.example .env
../.venv/bin/python -m pip install -e ".[dev]"
../.venv/bin/uvicorn app.main:app --reload
```

Consensus bridge:

```bash
cd backend
../.venv/bin/python -m consensus_bridge.main
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
- `EVIDENCE_MODE`
- `STRICT_LIVE_MODE`
- `CONSENSUS_MCP_ENABLED`
- `CONSENSUS_MCP_BRIDGE_URL`
- `CONSENSUS_MCP_SERVER_URL`
- `CONSENSUS_BRIDGE_HOST`
- `CONSENSUS_BRIDGE_PORT`
- `CONSENSUS_BRIDGE_HOME`
- `SEMANTIC_SCHOLAR_API_KEY`
- `PROTOCOLS_IO_TOKEN`
- `TAVILY_API_KEY`
- `RUN_LIVE_INTEGRATION`

## API Surface

- `GET /api/presets`
- `GET /api/readiness`
- `GET /api/runs`
- `POST /api/literature-qc`
- `POST /api/runs/{run_id}/plan`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `GET /api/runs/{run_id}/reviews`
- `POST /api/runs/{run_id}/reviews`
- `GET /api/runs/{run_id}/export/json`
- `GET /api/runs/{run_id}/export/citations`
- `GET /api/runs/{run_id}/export/procurement`
- `GET /api/runs/{run_id}/export/pdf`

Frontend runtime:

- `VITE_BACKEND_TARGET` configures the Vite dev proxy target and defaults to `http://localhost:8000`.
- `VITE_API_BASE_URL` is an optional override for unusual setups; normal local development should leave it unset.

## Local Dev

Start the backend on `http://localhost:8000` and the frontend on Vite. The frontend uses relative `/api` requests, and Vite proxies `/api` and `/health` to `VITE_BACKEND_TARGET`.

## Tunnel / Preview

For tunnel or deploy-preview access, keep the frontend using relative `/api` routes or set `VITE_API_BASE_URL` explicitly if the frontend and backend are on different origins. On the backend, allow those origins with `BACKEND_CORS_ALLOW_ORIGINS` and optionally `BACKEND_CORS_ALLOW_ORIGIN_REGEX` for dynamic preview hosts.

If provider keys are missing, the HeLa cryopreservation example hypothesis still works through deterministic seeded evidence. Other example hypotheses run through the same workflow with lower confidence and explicit evidence-gap warnings.

## Resource Routing

Literature QC is sequential and traceable.

- If `CONSENSUS_MCP_ENABLED=true`, Consensus is always attempted first.
- Consensus results are cached by normalized hypothesis text in SQLite.
- Consensus failures are recorded in `provider_trace` and do not stop Semantic Scholar or Europe PMC.
- The backend expects a local HTTP sidecar at `CONSENSUS_MCP_BRIDGE_URL`.
- The checked-in bridge uses `mcp-remote` to talk to `https://mcp.consensus.app/mcp` and keeps OAuth local to the developer machine.
- Europe PMC and Semantic Scholar run for every Literature QC.
- NCBI is only used as a biomedical fallback.
- arXiv is only used for diagnostics-biosensor and microbial-electrochemistry routes.
- Seeded fallback evidence is only used when live providers fail to produce usable results and strict live mode is off.

## Evidence Modes

The app supports three explicit evidence modes:

- `strict_live`
  - real providers only
  - no seeded fallback
  - best for proving the pipeline end to end
- `cached_live`
  - replays provider responses captured from a successful strict-live run
  - best mode for a stable judge demo
- `seeded_demo`
  - deterministic fallback for no-key or provider-outage resilience

The UI also reports the realized run outcome separately:

- `fully_live`
- `degraded_live`
- `demo_fallback`

Evidence Pack construction is domain-routed:

- `cell_biology`
  - ATCC, Thermo/Gibco, Promega, Sigma, protocols.io, OpenWetWare, literature methods, BMBL, inferred assumptions
- `diagnostics_biosensor`
  - literature methods, Tavily supplier search, Sigma or Thermo pages if retrieved, protocols.io, optional Bio-protocol discovery, STARD, inferred assumptions
- `animal_gut_health`
  - literature methods, Europe PMC or PubMed method evidence, protocols.io if relevant, OpenWetWare fallback, ARRIVE, MIQE if triggered, inferred assumptions
- `microbial_electrochemistry`
  - literature methods, Semantic Scholar or arXiv engineering evidence, protocols.io if relevant, explicit supplier search only, anaerobic or safety checklist if present, inferred assumptions

See [RESOURCE_ROUTING.md](RESOURCE_ROUTING.md) for the exact source order, query packs, known URLs, trust model, and guardrails.

## Guardrails

- Literature QC is required before plan generation.
- Catalog numbers and prices remain `null` unless directly retrieved.
- Missing catalog or price sets `requires_procurement_check: true`.
- Protocol steps include `evidence_source_ids`, confidence, and expert-review flags.
- The app uses “not found in searched sources,” not claims that work has never been done.
- Scientific standards can drive risks and review flags, but they do not act as direct protocol-parameter evidence.

## Tests

```bash
cd backend
pytest

cd ../frontend
npm test -- --run
npm run build
```

## Live HeLa Smoke

The first fully live path is the HeLa example hypothesis.

1. Add live secrets to `backend/.env`
2. Start the Consensus bridge:

```bash
cd backend
../.venv/bin/python -m consensus_bridge.main
```

3. Start the backend:

```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload
```

4. Start the frontend:

```bash
cd frontend
npm run dev
```

5. Optional live backend verification:

```bash
cd backend
RUN_LIVE_INTEGRATION=1 ../.venv/bin/pytest tests/test_live_integration.py -q
```

The live HeLa smoke should fail if seeded HeLa evidence appears in the final QC or plan sources while `STRICT_LIVE_MODE=true`.

## Review Memory

Scientist review is now implemented as structured review sessions stored against runs. The current loop is:

1. generate a plan
2. submit structured review items against sections, protocol steps, materials, budget, timeline, validation, or risks
3. persist those corrections
4. retrieve similar prior review items during future generation for the same domain route

This retrieval-memory loop ships now. Formal fine-tuning remains a later phase once enough reviewed examples and evals have been collected.
