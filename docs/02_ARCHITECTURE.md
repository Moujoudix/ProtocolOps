# ProtocolOps Architecture

## Overview

ProtocolOps is a two-tier web application with a local persistence layer and a provider orchestration layer for scientific planning.

Pipeline:

1. Natural-language scientific hypothesis
2. OpenAI structured hypothesis parsing
3. Literature QC
4. EvidencePack construction
5. OpenAI structured experiment-plan generation
6. UI rendering with evidence, confidence, source provenance, procurement status, expert-review flags, exports, and review memory

At runtime, the main code paths are:

- `backend/app/api/routes.py` for HTTP routes
- `backend/app/services/*` for orchestration
- `backend/app/providers/*` for external source access
- `frontend/src/*` for the React workspace

## Backend responsibilities

The FastAPI backend owns:

- hypothesis parsing and plan-generation calls to OpenAI structured outputs
- Literature QC orchestration and provider trace capture
- EvidencePack construction across literature, protocol, supplier, standards, and inferred layers
- persistence of runs, reviews, revisions, event history, and caches
- export endpoints for JSON, citations, procurement CSV, and PDF
- readiness reporting for live-provider status

Primary route families:

- `/health`
- `/api/presets`
- `/api/readiness`
- `/api/literature-qc`
- `/api/runs/*`

## Frontend responsibilities

The React + Vite frontend is a scientist-facing workspace. It:

- collects a free-text hypothesis or example hypothesis
- runs Literature QC and then plan generation
- renders the review-ready experiment plan
- exposes provenance through the Sources tab
- captures structured scientist review input
- surfaces run history, review memory, and exports

The frontend does not store provider secrets. It uses relative `/api` calls and relies on the Vite proxy in local development unless `VITE_API_BASE_URL` is explicitly set.

## Persistence layer

ProtocolOps uses SQLModel with SQLite by default.

Current SQLModel tables:

- `Run`: hypothesis, stage artifacts, review state, evidence mode, quality summary
- `ConsensusCache`: normalized-hypothesis cache for Consensus QC responses
- `EvidenceReplayCache`: cached-live replay artifacts
- `RunEvent`: stage-level event history
- `ReviewSession`: structured scientist review session
- `ReviewItem`: individual structured corrections
- `RunRevision`: child-to-parent revised plan relationship
- `PresentationAnchor`: label for the canonical demo run

The `Run` table stores structured artifacts as JSON blobs:

- `parsed_hypothesis_json`
- `literature_qc_json`
- `plan_json`
- `quality_summary_json`

SQLite compatibility migrations are handled in `backend/app/core/database.py` so older local DB files do not crash newer code paths.

## OpenAI structured outputs

ProtocolOps uses OpenAI structured outputs in two places:

1. `parse_hypothesis(...)`
   - model: `OPENAI_PARSE_MODEL`
   - output schema: `ParsedHypothesis`
2. `generate_plan(...)`
   - model: `OPENAI_PLAN_MODEL`
   - fallback: `OPENAI_FALLBACK_MODEL`
   - output schema: `ExperimentPlan`

Structured parsing is stage-isolated: no literature, supplier, protocol, or Tavily calls should happen during parsing.

If OpenAI is unavailable:

- non-strict modes can fall back to heuristic parsing / seeded demo behavior
- `strict_live` treats OpenAI failures as hard failures

## Provider and source layer

### Literature QC

Primary Literature QC providers:

1. Consensus MCP through the local HTTP bridge
2. Semantic Scholar
3. Europe PMC
4. NCBI E-utilities as biomedical fallback
5. arXiv for diagnostics / microbial-electrochemistry fallback

The provider trace is persisted in the QC artifact and later surfaced in the UI.

### EvidencePack

EvidencePack combines:

1. literature sources from Literature QC
2. protocol sources (`protocols.io`, OpenWetWare, optional Bio-protocol discovery)
3. supplier sources via Tavily search/extract and direct known URLs
4. scientific standards / checklists
5. explicitly labeled inferred assumptions

The EvidencePack stage is implemented in `backend/app/services/evidence_pack.py`.

### Consensus bridge

Consensus is accessed through `backend/consensus_bridge/main.py`, which exposes:

- `GET /health`
- `POST /search`

The bridge talks to `https://mcp.consensus.app/mcp` using `mcp-remote`, keeps OAuth local to the developer machine, and normalizes returned references into a backend-friendly shape.

## Domain routing

Current domain routes:

- `cell_biology`
- `diagnostics_biosensor`
- `animal_gut_health`
- `microbial_electrochemistry`

Routing is resolved from either:

- example hypothesis preset IDs, or
- hypothesis text heuristics / structured parsing output

Provider ordering and query packs live in:

- `backend/app/services/domain_routing.py`
- `backend/app/services/source_router.py`

## Plan generation

Plan generation requires both:

- a stored `ParsedHypothesis`
- a stored `LiteratureQC`

The plan-generation flow:

1. build an `EvidencePack`
2. retrieve similar structured review memory
3. call OpenAI with parsed hypothesis + QC summary + evidence summary + review memory
4. apply guardrails
5. score quality via `PlanQualitySummary`

Guardrails include:

- no invented catalog numbers
- no invented prices
- every protocol step must have `evidence_source_ids`
- inferred / adjacent / community methods remain expert-review-required

## Review memory

ProtocolOps includes a structured scientist review loop:

- review sessions are stored per run
- review items store target type, action, note, replacement text, and optional confidence override
- similar prior reviewed runs are ranked and retrieved at generation time
- applied review memory is visible in the plan UI

This is prompt-time retrieval of structured corrections. It is not a training or fine-tuning system.

## Exports

Current export endpoints:

- JSON
- citations
- procurement CSV
- PDF

JSON export is the full run state. Citations are plain text bullet references. Procurement CSV includes items that still need procurement follow-up.

## Evidence modes versus run outcomes

Configured evidence modes:

- `strict_live`
- `cached_live`
- `seeded_demo`

Realized run outcomes:

- `fully_live`
- `degraded_live`
- `demo_fallback`

Important distinction:

- `strict_live` is a configuration
- `degraded_live` is a result

Example:

- proof run `d4f6d470-5c47-4568-9eac-019815a80bb3`
  - configured mode: `strict_live`
  - realized outcome: `degraded_live`
  - reason: Semantic Scholar returned HTTP `429`, while Consensus, Europe PMC, and live supplier sources still succeeded

## Related docs

- [Docs hub](README.md)
- [API reference](05_API_REFERENCE.md)
- [Local setup and live mode](06_LOCAL_SETUP_AND_LIVE_MODE.md)
- [Scientist review loop](08_SCIENTIST_REVIEW_LOOP.md)
- [Submission notes](../SUBMISSION_NOTES.md)
