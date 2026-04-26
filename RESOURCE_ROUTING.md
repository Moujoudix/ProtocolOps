# Resource Routing

This document is the source-of-truth for how ProtocolOps routes scientific resources through the MVP pipeline.

## Global Pipeline

The app always follows this order:

1. User hypothesis
2. OpenAI structured hypothesis parsing
3. Literature QC
4. Evidence Pack construction
5. OpenAI structured experiment-plan generation
6. Frontend rendering with sources, confidence, and review flags

The experiment plan is never generated from the raw user prompt alone.

## Stage 1: Hypothesis Parsing

Stage 1 uses OpenAI only.

- No literature database calls
- No protocol repository calls
- No Tavily calls
- No supplier-page calls

Structured parsing extracts:

- `domain_route`
- `scientific_system`
- `model_or_organism`
- `intervention`
- `comparator`
- `outcome_metric`
- `success_threshold`
- `mechanism`
- `literature_query_terms`
- `protocol_query_terms`
- `supplier_material_query_terms`

Compatibility fields are still carried for one transition iteration:

- `organism_or_system`
- `outcome`
- `effect_size`
- `key_terms`

## Stage 2: Literature QC

Literature QC runs sequentially so provider order, fallback decisions, and `provider_trace` are deterministic.

### Global Literature QC Order

1. Consensus MCP
2. Semantic Scholar REST
3. Europe PMC REST
4. NCBI E-utilities for biomedical fallback
5. arXiv for engineering or electrochemistry fallback
6. Seeded fallback only if live providers fail

### Consensus Rules

- Controlled by `CONSENSUS_MCP_ENABLED=true`
- If enabled, Consensus is always attempted first
- Runtime access goes through the checked-in local Consensus sidecar, which exposes `POST /search`
- The sidecar connects to `https://mcp.consensus.app/mcp` through `mcp-remote` so OAuth stays local to the developer machine
- Cached by normalized hypothesis text in SQLite
- Maximum 1 live Consensus call per normalized hypothesis
- Cached results count as the first successful attempt
- If Consensus fails, the failure is recorded in `provider_trace` and the pipeline continues
- Consensus is used only during Literature QC, never during plan generation

Each `provider_trace` entry includes:

- `provider`
- `attempted`
- `succeeded`
- `cached`
- `query`
- `result_count`
- `error`

### Literature QC Decision Logic

The novelty classifier follows this order:

1. Same system + same intervention + same comparator + same outcome or method:
   - `novelty_signal = exact_match_found`
2. Same system or method family + related intervention or outcome:
   - `novelty_signal = similar_work_exists`
3. Otherwise:
   - `novelty_signal = not_found_in_searched_sources`

The app must never claim that something has never been done. The correct language is:

`No exact match was found in the configured searched sources.`

### Literature QC Output

Every `LiteratureQC` result includes:

- `novelty_signal`
- `confidence`
- `searched_sources`
- `provider_trace`
- `references`
- `literature_sources`
- `literature_synthesis`
- `rationale`
- `gaps`

### Domain Literature QC Order

#### `cell_biology` / HeLa

1. Consensus
2. Semantic Scholar
3. Europe PMC
4. NCBI fallback if biomedical evidence is weak
5. Seeded HeLa fallback if live providers fail

Representative queries:

- `trehalose HeLa cryopreservation viability DMSO`
- `trehalose mammalian cell cryopreservation post-thaw viability`
- `HeLa cryopreservation DMSO post-thaw viability`
- `trehalose cryoprotectant post-thaw viability mammalian cells`

#### `diagnostics_biosensor` / CRP

1. Consensus
2. Semantic Scholar
3. Europe PMC
4. arXiv
5. NCBI only if biomedical validation evidence is weak

Representative queries:

- `CRP electrochemical biosensor anti-CRP antibody whole blood`
- `paper-based electrochemical biosensor C-reactive protein detection`
- `C-reactive protein immunosensor ELISA sensitivity whole blood`
- `CRP biosensor 0.5 mg/L whole blood electrochemical`

#### `animal_gut_health` / Lactobacillus

1. Consensus
2. Europe PMC
3. Semantic Scholar
4. NCBI

Representative queries:

- `Lactobacillus rhamnosus GG C57BL/6 intestinal permeability FITC-dextran`
- `LGG tight junction claudin-1 occludin mouse gut permeability`
- `probiotic Lactobacillus rhamnosus GG FITC-dextran assay mice`

#### `microbial_electrochemistry` / Sporomusa

1. Consensus
2. Semantic Scholar
3. Europe PMC
4. arXiv

Representative queries:

- `Sporomusa ovata bioelectrochemical CO2 acetate cathode potential`
- `Sporomusa ovata microbial electrosynthesis acetate CO2`
- `-400 mV SHE Sporomusa ovata acetate production`

## Stage 3: Evidence Pack Construction

Evidence Pack construction uses a separate source recipe from Literature QC.

### Global Evidence Pack Order

1. Domain-specific authoritative source
2. Supplier or manufacturer source
3. Protocol repository
4. Community fallback protocol
5. Literature methods from Stage 2
6. Scientific standards or checklists
7. Seeded fallback evidence for demo reliability
8. Inferred assumptions, explicitly labeled

### Protocol Source Order

1. `protocols.io` REST API
2. OpenWetWare MediaWiki API
3. Bio-protocol via Tavily or Europe PMC, optional
4. Addgene for molecular workflows only, optional
5. Literature methods carried forward from QC
6. Inferred assumptions

### `protocols.io` Rules

- Primary protocol source
- Uses query expansion packs, not a single exact query
- Queries stop after 5 unique results are collected or the pack is exhausted
- Evidence classification:
  - `exact_match`
  - `close_match`
  - `adjacent_method`
  - `generic_method`
- `adjacent_method` and `generic_method` imply `expert_review_required = true`

### OpenWetWare Rules

- Community fallback protocol source
- Uses `https://openwetware.org/mediawiki/api.php`
- Never uses `https://openwetware.org/api.php`
- Community-level findings stay low trust and review-required

### Tavily Rules

- Known URL -> Tavily Extract
- Unknown URL -> Tavily Search -> selected URLs -> Tavily Extract
- Do not use Tavily Crawl
- Do not use Tavily Research

Search defaults:

- `search_depth = basic`
- `max_results = 5`
- `include_answer = none`
- `include_raw_content = false`
- `include_usage = true`

Extract defaults:

- `extract_depth = advanced`
- `format = markdown`
- `include_images = false`
- `include_usage = true`

### Domain Evidence Pack Recipes

#### `cell_biology` / HeLa

1. ATCC `CCL-2`
2. Thermo/Gibco cell-freezing guidance
3. Promega CellTiter-Glo
4. Sigma/Merck trehalose
5. `protocols.io` cryopreservation query pack
6. OpenWetWare freeze-thaw pages
7. Literature methods from QC results
8. BMBL checklist
9. Inferred assumptions

Known HeLa URLs:

- `https://www.atcc.org/products/ccl-2`
- `https://www.thermofisher.com/us/en/home/references/gibco-cell-culture-basics/cell-culture-protocols/freezing-cells.html`
- `https://worldwide.promega.com/resources/protocols/technical-bulletins/0/celltiter-glo-luminescent-cell-viability-assay-protocol/`

If Tavily is unavailable, known HeLa supplier sources fall back to validated seeded evidence objects.

#### `diagnostics_biosensor` / CRP

1. Literature methods from retrieved papers
2. Tavily supplier search for anti-CRP antibody and CRP assay materials
3. Sigma anti-CRP antibody pages if retrieved
4. Thermo CRP ELISA pages if retrieved
5. `protocols.io` biosensor query pack
6. Optional Bio-protocol discovery
7. STARD checklist
8. Inferred assumptions

Expected confidence is medium for materials and low-to-medium for operational protocol details. Many items may remain review-required.

#### `animal_gut_health` / Lactobacillus

1. Literature methods from retrieved papers
2. Europe PMC or PubMed method evidence
3. `protocols.io` if a relevant gut-permeability or FITC-dextran protocol is found
4. OpenWetWare Lactobacillus culture as community fallback only
5. ARRIVE checklist
6. MIQE checklist if qPCR appears
7. Inferred assumptions

Hard guardrail:

Do not generate animal dosing, housing, gavage, FITC-dextran dose, sample size, or euthanasia details unless they are source-backed.

#### `microbial_electrochemistry` / Sporomusa

1. Literature methods from retrieved papers
2. Semantic Scholar or arXiv engineering papers
3. `protocols.io` only if a relevant bioelectrochemical protocol is found
4. Supplier search only for explicit material needs
5. Anaerobic or safety checklist if implemented
6. Inferred assumptions

Hard guardrail:

Cathode potential, reactor design, CO2 delivery, anaerobic handling, acetate quantification, and benchmarks must be source-backed or review-required.

## Scientific Standards

Standards are static checklist evidence. They shape review flags and risk sections, but they do not act as direct protocol-parameter evidence.

### Supported Standards

- `MIQE`
  - qPCR
  - RT-qPCR
  - gene expression
  - claudin-1 / occludin expression
- `ARRIVE`
  - animal experiments
  - mouse models
  - in vivo probiotic studies
- `BMBL`
  - human cell lines
  - BSL-2 handling
  - HPV-containing HeLa
  - blood or microbial safety contexts
- `STARD`
  - diagnostic accuracy
  - CRP biosensor validation

## Trust Model

### Trust Level

1. `high`
2. `medium`
3. `low`

### High Trust

- Consensus synthesis when source-backed
- Peer-reviewed literature
- ATCC documentation
- Thermo / Promega supplier protocol for their own products
- Scientific standards

### Medium Trust

- Semantic Scholar metadata
- Europe PMC metadata
- protocols.io public protocols
- Supplier product pages
- Tavily-extracted supplier documentation

### Low Trust

- OpenWetWare community protocol
- Generic web page discovery
- LLM-inferred assumptions

### Provenance (`trust_tier`)

- `literature_database`
- `supplier_documentation`
- `community_protocol`
- `scientific_standard`
- `inferred`

### Evidence Class

1. `exact_match`
2. `close_match`
3. `adjacent_method`
4. `generic_method`
5. `supplier_reference`
6. `safety_or_standard`
7. `assumption`

Behavior:

- `exact_match + high trust` can be treated as strongly source-backed
- `close_match` is source-backed but may still carry medium confidence
- `adjacent_method`, `generic_method`, community protocol, and `assumption` require expert review

## Catalog and Price Guardrails

Catalog numbers are only allowed when directly supported by:

- supplier pages
- protocol material fields
- validated seeded evidence
- extracted documentation

If a catalog number is missing:

```json
{
  "catalog_number": null,
  "procurement_status": "requires_procurement_check"
}
```

Exact prices are allowed only when visibly present in a source. If pricing is missing, region-specific, login-gated, or hidden behind contact flows:

```json
{
  "price_status": "requires_procurement_check"
}
```

or

```json
{
  "price_status": "contact_supplier"
}
```

The app never invents exact prices.

## Non-MVP Sources

These are intentionally not runtime dependencies in the MVP:

- Google Scholar scraping
- Europe PMC SOAP, OAI, FTP, bulk downloads, Grants API
- Nature Protocols full extraction
- JoVE extraction
- Crossref as a core source
- OpenAlex as a core source
- Live browser automation scraping
- protocols.io OAuth or PDF endpoint
- Tavily Crawl
- Tavily Research

Possible later additions:

- Bio-protocol direct integration
- deeper Addgene integration
- Europe PMC Annotations
- Consensus API credentials outside MCP
- OpenAlex or Crossref enrichment
