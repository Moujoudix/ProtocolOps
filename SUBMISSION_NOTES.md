# Submission Notes

## Verified proof run

ProtocolOps includes a verified HeLa strict-live proof run:

- Run ID: `d4f6d470-5c47-4568-9eac-019815a80bb3`
- `status=plan_complete`
- `evidence_mode=strict_live`
- `used_seed_data=false`
- `run_mode=degraded_live`

## Why the proof run is degraded-live

The run is not labeled `fully_live` because:

- Semantic Scholar returned HTTP `429`

The run still completed using other live providers:

- Consensus MCP via the local sidecar bridge
- Europe PMC
- live supplier evidence

## Consensus and supplier verification

Consensus OAuth was verified through the local bridge.

Live supplier evidence for the proof run was retrieved from:

- `www.atcc.org`
- `www.thermofisher.com`
- `worldwide.promega.com`
- `www.sigmaaldrich.com`

## Cached-live availability

After the strict-live proof run completed successfully without seeded evidence, cached-live replay became available for the same hypothesis.

## Limitations

- ProtocolOps generates a review-ready experiment plan, not a final lab-approved SOP.
- Semantic Scholar public-mode rate limiting can degrade otherwise live runs.
- Catalog numbers and prices remain `null` unless directly retrieved from evidence.
- Review memory is prompt-time retrieval of structured scientist corrections, not fine-tuning.
- Screenshot automation is not bundled in this repository; screenshots should be captured manually from the live app when preparing submission assets.

