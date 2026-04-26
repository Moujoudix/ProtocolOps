from typing import Any

import httpx

from app.core.config import Settings
from app.models.schemas import EvidenceSource, EvidenceType, TrustTier, now_utc
from app.providers.base import SearchContext
from app.providers.utils import classify_evidence, compact_text, stable_source_id


class SemanticScholarProvider:
    name = "Semantic Scholar"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, context: SearchContext) -> list[EvidenceSource]:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": 3,
            "fields": "title,url,abstract,year,authors,externalIds,venue,publicationDate",
        }
        headers = {}
        if self.settings.semantic_scholar_api_key:
            headers["x-api-key"] = self.settings.semantic_scholar_api_key

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError:
            return []

        payload = response.json()
        return [self._normalize(item, context) for item in payload.get("data", [])[:3]]

    def _normalize(self, item: dict[str, Any], context: SearchContext) -> EvidenceSource:
        title = item.get("title") or "Untitled Semantic Scholar result"
        snippet = compact_text(item.get("abstract") or item.get("venue") or "No abstract returned by provider.")
        external_ids = item.get("externalIds") or {}
        authors = [author.get("name", "") for author in item.get("authors", []) if author.get("name")]
        evidence_type = classify_evidence(
            context.parsed_hypothesis,
            title,
            snippet,
            EvidenceType.adjacent_evidence,
        )
        return EvidenceSource(
            id=stable_source_id("s2", item.get("paperId"), title),
            source_name=self.name,
            title=title,
            url=item.get("url"),
            evidence_type=evidence_type,
            trust_tier=TrustTier.literature_database,
            snippet=snippet,
            authors=authors[:6],
            year=item.get("year"),
            doi=external_ids.get("DOI"),
            confidence=0.72 if evidence_type == EvidenceType.exact_evidence else 0.58,
            retrieved_at=now_utc(),
        )


class EuropePmcProvider:
    name = "Europe PMC"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, context: SearchContext) -> list[EvidenceSource]:
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": 3,
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
        except httpx.HTTPError:
            return []

        payload = response.json()
        results = payload.get("resultList", {}).get("result", [])
        return [self._normalize(item, context) for item in results[:3]]

    def _normalize(self, item: dict[str, Any], context: SearchContext) -> EvidenceSource:
        title = item.get("title") or "Untitled Europe PMC result"
        snippet = compact_text(item.get("abstractText") or item.get("journalTitle") or "No abstract returned by provider.")
        doi = item.get("doi")
        url = f"https://europepmc.org/article/{item.get('source')}/{item.get('id')}" if item.get("source") and item.get("id") else None
        evidence_type = classify_evidence(
            context.parsed_hypothesis,
            title,
            snippet,
            EvidenceType.adjacent_evidence,
        )
        return EvidenceSource(
            id=stable_source_id("epmc", item.get("source"), item.get("id"), title),
            source_name=self.name,
            title=title,
            url=url,
            evidence_type=evidence_type,
            trust_tier=TrustTier.literature_database,
            snippet=snippet,
            authors=[name.strip() for name in (item.get("authorString") or "").split(",") if name.strip()][:6],
            year=_safe_int(item.get("pubYear")),
            doi=doi,
            confidence=0.7 if evidence_type == EvidenceType.exact_evidence else 0.55,
            retrieved_at=now_utc(),
        )


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
