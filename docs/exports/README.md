# Exported Proof-Run Artifacts

These files are generated from the verified HeLa proof run:

- Run ID: `d4f6d470-5c47-4568-9eac-019815a80bb3`

## Files

- `anchor_hela_run.json`
  - full exported run payload from the JSON export endpoint
- `anchor_hela_citations.md`
  - citation export captured from the plain-text citations endpoint and stored as Markdown for easy repository browsing
- `anchor_hela_procurement.csv`
  - procurement follow-up items that still need catalog or price confirmation
- `anchor_hela_provider_trace.json`
  - Literature QC provider trace extracted from the proof-run payload
- `readiness_snapshot.json`
  - readiness state captured from the backend at export time

## What these prove

- the strict-live HeLa path completed successfully without seeded evidence
- the realized run outcome was `degraded_live`, not `fully_live`
- live supplier evidence was present
- the app can export machine-readable planning artifacts suitable for review and submission packaging

