import asyncio

from app.core.config import Settings
from app.models.schemas import EvidenceSource, EvidenceType, LiteratureQC, NoveltySignal
from app.providers.base import SearchContext
from app.providers.literature import EuropePmcProvider, SemanticScholarProvider
from app.seeds.hela import is_hela_trehalose_hypothesis, seeded_hela_literature_qc, seeded_hela_sources


class LiteratureQcService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.providers = [SemanticScholarProvider(settings), EuropePmcProvider(settings)]

    async def run(self, context: SearchContext) -> LiteratureQC:
        if should_use_seed_only(self.settings, context):
            return seeded_hela_literature_qc()

        if self.settings.app_env == "test" and is_hela_trehalose_hypothesis(
            context.parsed_hypothesis.original_text,
            context.preset_id,
        ):
            return seeded_hela_literature_qc()

        query = build_literature_query(context)
        provider_results = await asyncio.gather(
            *(provider.search(query, context) for provider in self.providers),
            return_exceptions=True,
        )
        sources: list[EvidenceSource] = []
        for result in provider_results:
            if isinstance(result, Exception):
                continue
            sources.extend(result)

        if is_hela_trehalose_hypothesis(context.parsed_hypothesis.original_text, context.preset_id):
            sources = merge_by_id(seeded_hela_sources() + sources)

        top_refs = sorted(sources, key=lambda source: source.confidence, reverse=True)[:3]
        searched_sources = [provider.name for provider in self.providers]
        if is_hela_trehalose_hypothesis(context.parsed_hypothesis.original_text, context.preset_id):
            searched_sources.append("HeLa demo seed")

        novelty_signal = classify_novelty(top_refs)
        confidence = confidence_for(novelty_signal, top_refs)
        return LiteratureQC(
            novelty_signal=novelty_signal,
            confidence=confidence,
            references=top_refs,
            searched_sources=searched_sources,
            rationale=build_rationale(novelty_signal, top_refs),
            evidence_gap_warnings=build_warnings(context, top_refs),
        )


def build_literature_query(context: SearchContext) -> str:
    parsed = context.parsed_hypothesis
    terms = parsed.key_terms[:6]
    if parsed.organism_or_system:
        terms.insert(0, parsed.organism_or_system)
    if parsed.outcome:
        terms.append(parsed.outcome)
    deduped = []
    for term in terms:
        if term and term not in deduped:
            deduped.append(term)
    return " ".join(deduped) or parsed.original_text[:200]


def classify_novelty(references: list[EvidenceSource]) -> NoveltySignal:
    if any(source.evidence_type == EvidenceType.exact_evidence for source in references):
        return NoveltySignal.exact_match_found
    if references:
        return NoveltySignal.similar_work_exists
    return NoveltySignal.not_found_in_searched_sources


def confidence_for(signal: NoveltySignal, references: list[EvidenceSource]) -> float:
    if not references:
        return 0.31
    avg = sum(source.confidence for source in references) / len(references)
    if signal == NoveltySignal.exact_match_found:
        return min(0.9, avg + 0.12)
    if signal == NoveltySignal.similar_work_exists:
        return min(0.78, avg + 0.05)
    return min(0.45, avg)


def build_rationale(signal: NoveltySignal, references: list[EvidenceSource]) -> str:
    if signal == NoveltySignal.exact_match_found:
        return "At least one searched source appears to match the key system, intervention, comparator, and outcome."
    if signal == NoveltySignal.similar_work_exists:
        return (
            "Searched sources returned adjacent or generic evidence related to the hypothesis, but an exact "
            "match was not confirmed in the searched sources."
        )
    return "No matching references were found in the searched sources used by this MVP run."


def build_warnings(context: SearchContext, references: list[EvidenceSource]) -> list[str]:
    warnings = [
        "Do not interpret this as exhaustive novelty review; it only covers the searched sources.",
        "Use 'not found in searched sources' rather than claiming the work has never been done.",
    ]
    if not references:
        warnings.append("Provider results were empty or unavailable, so downstream plans should be low confidence.")
    if context.preset_id != "hela-trehalose":
        warnings.append("This non-HeLa path has no deep seeded evidence and should carry stronger expert-review flags.")
    return warnings


def merge_by_id(sources: list[EvidenceSource]) -> list[EvidenceSource]:
    seen: set[str] = set()
    merged: list[EvidenceSource] = []
    for source in sources:
        if source.id in seen:
            continue
        seen.add(source.id)
        merged.append(source)
    return merged


def should_use_seed_only(settings: Settings, context: SearchContext) -> bool:
    is_seeded_demo = is_hela_trehalose_hypothesis(context.parsed_hypothesis.original_text, context.preset_id)
    has_live_keys = bool(settings.semantic_scholar_api_key or settings.tavily_api_key or settings.protocols_io_token)
    return is_seeded_demo and not has_live_keys
