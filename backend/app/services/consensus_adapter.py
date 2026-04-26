from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.models.schemas import EvidenceSource, EvidenceType, TrustLevel, TrustTier, now_utc
from app.providers.base import ProviderSearchResult, SearchContext
from app.providers.utils import classify_evidence, compact_text, stable_source_id


class ConsensusMcpAdapter:
    name = "Consensus"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, context: SearchContext) -> ProviderSearchResult:
        if not self.settings.consensus_mcp_enabled:
            return ProviderSearchResult(sources=[])
        if not self.settings.consensus_mcp_bridge_url:
            raise RuntimeError("Consensus MCP bridge not configured")

        body = {
            "hypothesis": context.parsed_hypothesis.original_text,
            "query": query,
            "domain_route": context.parsed_hypothesis.domain_route,
            "literature_query_terms": context.parsed_hypothesis.literature_query_terms,
        }
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(self.settings.consensus_mcp_bridge_url, json=body)
            response.raise_for_status()

        payload = response.json()
        items = payload.get("references") or payload.get("sources") or []
        sources = [self._normalize(item, context) for item in items[:5]]
        synthesis = payload.get("literature_synthesis") or payload.get("synthesis")
        return ProviderSearchResult(sources=sources, literature_synthesis=synthesis)

    def _normalize(self, item: dict[str, Any], context: SearchContext) -> EvidenceSource:
        title = item.get("title") or "Consensus literature synthesis result"
        snippet = compact_text(item.get("snippet") or item.get("summary") or "Consensus synthesis result.")
        evidence_type = classify_evidence(context.parsed_hypothesis, title, snippet, EvidenceType.close_match)
        return EvidenceSource(
            id=stable_source_id("consensus", item.get("doi"), item.get("url"), title),
            source_name=self.name,
            title=title,
            url=item.get("url"),
            evidence_type=evidence_type,
            trust_tier=TrustTier.literature_database,
            trust_level=TrustLevel.high,
            snippet=snippet,
            authors=[author for author in item.get("authors", []) if author][:6],
            year=item.get("year"),
            doi=item.get("doi"),
            confidence=min(0.9, float(item.get("confidence", 0.78))),
            retrieved_at=now_utc(),
        )
