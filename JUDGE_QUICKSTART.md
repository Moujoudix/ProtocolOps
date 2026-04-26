# ProtocolOps Judge Quickstart

## What ProtocolOps does

ProtocolOps turns a natural-language scientific hypothesis into a review-ready experiment plan with Literature QC, evidence provenance, procurement follow-up, and structured scientist review memory. It is designed to compress the manual scoping work that usually happens before a lab or CRO turns a hypothesis into an operational proposal.

## Recommended demo path

Use the HeLa cryopreservation example:

- `Main demo / HeLa cryopreservation`

This is the strongest verified path in the repository and has a strict-live proof run on record.

## How to open the app

Frontend:

- `http://127.0.0.1:5175/`

Backend:

- `http://127.0.0.1:8002/`

Consensus bridge health:

- `http://127.0.0.1:8765/health`

## What to click

1. Open the app.
2. In `Example hypotheses`, choose `Main demo / HeLa cryopreservation`.
3. Click `Run Literature QC`.
4. Inspect the novelty signal, confidence, and references.
5. Click `Generate Plan`.
6. Walk through:
   - `Overview`
   - `Materials`
   - `Sources`
   - `Review`

## What to inspect

Focus on:

- novelty signal and references from Literature QC
- source-backed versus inferred sections
- procurement-check items in materials and budget
- live supplier domains in the Sources tab
- review-ready warnings and expert-review flags

## How to interpret modes

### `strict_live`

Configured mode meaning:

- the app is attempting to use real providers only
- seeded fallback is forbidden

### `degraded_live`

Realized outcome meaning:

- the run completed with live providers
- at least one live provider partially failed

This is the honest status of the verified HeLa proof run because Semantic Scholar returned HTTP `429`.

### `cached_live`

Configured mode meaning:

- the app replays evidence captured from a prior successful live run
- this is the most stable mode for a live demo once a proof run has been recorded

## Important note

ProtocolOps generates a **review-ready experiment plan**. It does not claim to generate a final lab-approved SOP.

