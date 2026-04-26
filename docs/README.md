# ProtocolOps Docs Hub

This directory collects the main technical and submission-facing documentation for ProtocolOps.

## Product and overview

- [Architecture](02_ARCHITECTURE.md)
- [API reference](05_API_REFERENCE.md)
- [Evaluation checklist](../EVALUATION_CHECKLIST.md)
- [Submission notes](../SUBMISSION_NOTES.md)

## Setup and runtime

- [Local setup and live mode](06_LOCAL_SETUP_AND_LIVE_MODE.md)
- [Judge quickstart](../JUDGE_QUICKSTART.md)
- [Resource routing spec](../RESOURCE_ROUTING.md)

## Review and safety

- [Scientist review loop](08_SCIENTIST_REVIEW_LOOP.md)
- [Security and secrets](../SECURITY_AND_SECRETS.md)

## Visual assets

- [Diagram browser](diagrams/README.md)
- [Video page](videos.html)
- [Screenshot capture checklist](screenshots/README.md)

## Proof-run artifacts

- [Exports overview](exports/README.md)
- [OpenAPI snapshot](openapi.json)

## Glossary

- **Literature QC**: the novelty and reference-check step run before plan generation.
- **EvidencePack**: the combined evidence layer built from literature, protocol, supplier, standards, and inferred sources.
- **strict_live**: configured mode that allows only real providers and forbids seeded fallback.
- **degraded_live**: realized run outcome where a live run completed but one or more providers partially failed.
- **cached_live**: configured replay mode that uses artifacts captured from a prior successful live run.
- **seeded_demo**: deterministic fallback mode used for no-key or provider-outage scenarios.
- **review memory**: prompt-time retrieval of structured scientist corrections from prior reviewed runs.

