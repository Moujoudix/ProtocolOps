# ProtocolOps Evaluation Checklist

| Challenge requirement | Current implementation | Verified locally |
| --- | --- | --- |
| Natural-language scientific input | Free-text hypothesis entry in the React workspace and `POST /api/literature-qc` | Yes |
| Literature QC step | Dedicated QC stage with structured output, provider trace, and stored QC artifact | Yes |
| Novelty signal | `exact_match_found`, `similar_work_exists`, `not_found_in_searched_sources` | Yes |
| 1–3 references | `LiteratureQC.references` stores up to 3 top references | Yes |
| Full experiment plan | `ExperimentPlan` schema with overview, protocol, materials, budget, timeline, validation, risks, and sources | Yes |
| Protocol | Ordered `protocol` steps with `evidence_source_ids`, confidence, and review flags | Yes |
| Materials and supply chain | `materials` plus supplier-domain evidence and procurement statuses | Yes |
| Budget | `budget.items` with procurement and price guardrails | Yes |
| Timeline | `timeline` section in the generated plan | Yes |
| Validation | `validation` section in the generated plan | Yes |
| Source provenance | `sources` list, trust model, provider trace, and Sources tab | Yes |
| Scientist review loop | review sessions, review items, revision endpoint, comparison view, review memory | Yes |
| Guardrails against invented catalog numbers | `catalog_number` stays `null` unless retrieved; procurement status flips to follow-up | Yes |
| Guardrails against invented prices | `price` stays `null` unless retrieved; `price_status` reflects follow-up needed | Yes |
| Four official example hypotheses | `GET /api/presets` exposes HeLa, CRP, Lactobacillus, and Sporomusa examples | Yes |
| Custom input support | Users can overwrite the example hypothesis and run the same pipeline | Yes |
| Strict-live proof path | verified HeLa proof run under `strict_live` with `used_seed_data=false` | Yes |
| Honest degraded-live reporting | run outcome becomes `degraded_live` when live providers partially fail | Yes |
| Export surfaces | JSON, citations, procurement CSV, and PDF endpoints | Yes |
| Review memory visibility | `memory_applied` data is rendered in the UI when relevant | Yes |
| Final lab-approved SOP generation | Not implemented; output is review-ready, not final SOP | N/A by design |
| Fine-tuning loop | Not implemented; current learning loop is retrieval of structured corrections | N/A by design |

