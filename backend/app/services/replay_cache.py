from __future__ import annotations

from sqlmodel import Session

from app.models.db import EvidenceReplayCache, utc_now
from app.models.schemas import EvidencePack, LiteratureQC, ProviderTraceEntry, model_from_json
from app.providers.utils import normalize_hypothesis_key


class EvidenceReplayCacheService:
    def get(
        self,
        session: Session | None,
        hypothesis: str,
    ) -> EvidenceReplayCache | None:
        if session is None:
            return None
        return session.get(EvidenceReplayCache, normalize_hypothesis_key(hypothesis))

    def load_literature_qc(
        self,
        session: Session | None,
        hypothesis: str,
    ) -> LiteratureQC | None:
        record = self.get(session, hypothesis)
        if record is None:
            return None
        cached = model_from_json(LiteratureQC, record.literature_qc_json)
        if cached is None:
            return None
        trace = [mark_trace_cached(entry) for entry in cached.provider_trace]
        return cached.model_copy(
            update={
                "provider_trace": trace,
                "searched_sources": dedupe_strings([*cached.searched_sources, "Cached live replay"]),
            }
        )

    def load_evidence_pack(
        self,
        session: Session | None,
        hypothesis: str,
    ) -> EvidencePack | None:
        record = self.get(session, hypothesis)
        if record is None:
            return None
        cached = model_from_json(EvidencePack, record.evidence_pack_json)
        if cached is None:
            return None
        trace = [mark_trace_cached(entry) for entry in cached.provider_trace]
        warnings = dedupe_strings([*cached.evidence_gap_warnings, "Cached live evidence replayed from a prior successful live run."])
        return cached.model_copy(
            update={
                "provider_trace": trace,
                "searched_providers": dedupe_strings([*cached.searched_providers, "Cached live replay"]),
                "evidence_gap_warnings": warnings,
            }
        )

    def store(
        self,
        session: Session | None,
        *,
        hypothesis: str,
        preset_id: str | None,
        literature_qc: LiteratureQC,
        evidence_pack: EvidencePack,
        source_run_id: str | None,
    ) -> None:
        if session is None:
            return
        session.merge(
            EvidenceReplayCache(
                normalized_hypothesis=normalize_hypothesis_key(hypothesis),
                preset_id=preset_id,
                literature_qc_json=literature_qc.model_dump_json(),
                evidence_pack_json=evidence_pack.model_dump_json(),
                source_run_id=source_run_id,
                updated_at=utc_now(),
            )
        )
        session.commit()


def mark_trace_cached(entry: ProviderTraceEntry) -> ProviderTraceEntry:
    return entry.model_copy(update={"cached": True, "fallback_used": True})


def dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped
