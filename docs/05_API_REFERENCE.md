# ProtocolOps API Reference

The backend is a FastAPI app mounted at `/api` plus a root health endpoint.

## Endpoint table

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | basic backend liveness |
| `GET` | `/api/readiness` | provider readiness, evidence mode, cached-live availability |
| `GET` | `/api/presets` | official example hypotheses |
| `GET` | `/api/runs` | recent runs list |
| `POST` | `/api/literature-qc` | parse hypothesis and run Literature QC |
| `POST` | `/api/runs/{run_id}/plan` | generate the review-ready experiment plan |
| `GET` | `/api/runs/{run_id}` | fetch full run state |
| `GET` | `/api/runs/{run_id}/events` | stage event timeline |
| `GET` | `/api/runs/{run_id}/reviews` | structured review history |
| `POST` | `/api/runs/{run_id}/reviews` | submit structured scientist review |
| `GET` | `/api/runs/{run_id}/export/json` | export full run JSON |
| `GET` | `/api/runs/{run_id}/export/citations` | export citations as plain text |
| `GET` | `/api/runs/{run_id}/export/procurement` | export procurement follow-up CSV |

## Additional live endpoints

These routes also exist in the current app:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/runs/{run_id}/revise` | generate a revised plan from structured review memory |
| `GET` | `/api/runs/{run_id}/comparison` | compare baseline and revised plans |
| `POST` | `/api/runs/{run_id}/presentation-anchor` | mark a run as the presentation anchor |
| `GET` | `/api/runs/{run_id}/export/pdf` | export a PDF summary |

## Core examples

### `GET /health`

Response:

```json
{
  "status": "ok"
}
```

### `GET /api/readiness`

Response excerpt:

```json
{
  "strict_live_mode": true,
  "evidence_mode": "strict_live",
  "live_ready": true,
  "cached_live_available": true,
  "seeded_demo_available": true,
  "providers": [
    {
      "provider": "OpenAI",
      "status": "ready",
      "detail": "Structured parsing and plan generation",
      "configured": true,
      "authenticated": true
    }
  ]
}
```

### `GET /api/presets`

Returns the official example hypotheses shown in the UI.

Response excerpt:

```json
[
  {
    "id": "hela-trehalose",
    "label": "Main demo / HeLa cryopreservation",
    "domain": "cell biology",
    "optimized_demo": true,
    "hypothesis": "Replacing sucrose with trehalose..."
  }
]
```

### `POST /api/literature-qc`

Request:

```json
{
  "hypothesis": "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard DMSO protocol, due to trehalose's superior membrane stabilization at low temperatures.",
  "preset_id": "hela-trehalose"
}
```

Response shape:

```json
{
  "run_id": "uuid",
  "parsed_hypothesis": {
    "domain_route": "cell_biology",
    "scientific_system": "cell culture cryopreservation",
    "literature_query_terms": ["..."]
  },
  "literature_qc": {
    "novelty_signal": "exact_match_found",
    "confidence": 0.78,
    "references": [],
    "literature_sources": [],
    "searched_sources": ["Consensus", "Semantic Scholar", "Europe PMC"],
    "provider_trace": []
  }
}
```

### `POST /api/runs/{run_id}/plan`

Request body: none

Response shape:

```json
{
  "run_id": "uuid",
  "plan": {
    "plan_title": "Review-ready experimental plan: ...",
    "quality_summary": {
      "operational_readiness": 0.44
    },
    "overview": {},
    "protocol": [],
    "materials": [],
    "budget": {},
    "timeline": {},
    "validation": {},
    "risks": {},
    "sources": []
  }
}
```

### `GET /api/runs/{run_id}`

Returns the full run state, including:

- `run_mode`
- `evidence_mode`
- `used_seed_data`
- `parsed_hypothesis`
- `literature_qc`
- `plan`

This is the canonical payload behind JSON export and run rehydration in the frontend.

### `GET /api/runs`

Returns lightweight recent-run records for the left-rail history.

Example fields:

```json
{
  "run_id": "uuid",
  "hypothesis": "Replacing sucrose with trehalose...",
  "status": "plan_complete",
  "review_state": "generated",
  "run_mode": "degraded_live",
  "evidence_mode": "strict_live",
  "domain": "cell biology",
  "plan_title": "Review-ready experimental plan: ..."
}
```

### `GET /api/runs/{run_id}/events`

Returns ordered stage events such as:

- `hypothesis_parse`
- `literature_qc`
- `evidence_pack`
- `plan_generation`
- `review`
- `presentation_anchor`

### `GET /api/runs/{run_id}/reviews`

Returns saved review sessions with nested review items.

### `POST /api/runs/{run_id}/reviews`

Request example:

```json
{
  "reviewer_name": "Scientist reviewer",
  "summary": "Need stronger caution around formulation assumptions",
  "review_state": "reviewed",
  "items": [
    {
      "target_type": "section",
      "target_key": "overview",
      "action": "comment",
      "comment": "Clarify that trehalose concentration remains expert-review-required.",
      "replacement_text": null,
      "confidence_override": null
    }
  ]
}
```

Response:

```json
{
  "review": {
    "id": "uuid",
    "run_id": "uuid",
    "review_state": "reviewed",
    "items": []
  }
}
```

## Export endpoints

### `GET /api/runs/{run_id}/export/json`

- content type: `application/json`
- payload: full `RunStateResponse`

### `GET /api/runs/{run_id}/export/citations`

- content type: `text/plain`
- payload: plain text bullet list of references

Even if a checked-in artifact is stored as `.md`, the API itself returns plain text.

### `GET /api/runs/{run_id}/export/procurement`

- content type: `text/csv`
- rows only include items that still need procurement follow-up

### `GET /api/runs/{run_id}/export/pdf`

- content type: `application/pdf`
- intended as a printable summary, not a final lab SOP

## Related docs

- [Docs hub](README.md)
- [Architecture](02_ARCHITECTURE.md)
- [Local setup and live mode](06_LOCAL_SETUP_AND_LIVE_MODE.md)
- [Scientist review loop](08_SCIENTIST_REVIEW_LOOP.md)
- [Submission notes](../SUBMISSION_NOTES.md)
