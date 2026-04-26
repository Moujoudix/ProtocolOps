from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.models.schemas import EvidenceSource, EvidenceType, TrustLevel, TrustTier, now_utc
from app.providers.base import ProviderSearchResult, SearchContext
from app.providers.utils import classify_evidence, compact_text, host_from_url, stable_source_id


class ProtocolsIoProvider:
    name = "protocols.io"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, context: SearchContext) -> ProviderSearchResult:
        if not self.settings.protocols_io_token:
            return ProviderSearchResult(sources=[])

        url = "https://www.protocols.io/api/v3/protocols"
        params = {
            "filter": "public",
            "key": query,
            "order_field": "relevance",
            "order_dir": "desc",
            "page_size": 5,
        }
        headers = {"Authorization": f"Bearer {self.settings.protocols_io_token}"}
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

        payload = response.json()
        sources = [self._normalize(item, context) for item in payload.get("items", [])[:5]]
        return ProviderSearchResult(sources=sources)

    def _normalize(self, item: dict[str, Any], context: SearchContext) -> EvidenceSource:
        uri = item.get("uri")
        url = item.get("url") or (f"https://www.protocols.io/view/{uri}" if uri else None)
        title = item.get("title") or "Untitled protocols.io result"
        snippet = compact_text(item.get("description") or item.get("materials_text") or "Public protocol metadata result.")
        evidence_type = classify_evidence(context.parsed_hypothesis, title, snippet, EvidenceType.generic_method)
        if evidence_type == EvidenceType.close_match:
            evidence_type = EvidenceType.adjacent_method
        return EvidenceSource(
            id=stable_source_id("pio", str(item.get("id")), uri, title),
            source_name=self.name,
            title=title,
            url=url,
            evidence_type=evidence_type,
            trust_tier=TrustTier.community_protocol,
            trust_level=TrustLevel.medium if evidence_type != EvidenceType.generic_method else TrustLevel.low,
            snippet=snippet,
            authors=[],
            year=None,
            doi=item.get("doi"),
            confidence=0.62 if evidence_type != EvidenceType.generic_method else 0.53,
            retrieved_at=now_utc(),
        )


class OpenWetWareProvider:
    name = "OpenWetWare"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, context: SearchContext) -> ProviderSearchResult:
        url = "https://openwetware.org/mediawiki/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 5,
        }
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        payload = response.json()
        sources = [self._normalize(item, context) for item in payload.get("query", {}).get("search", [])[:5]]
        return ProviderSearchResult(sources=sources)

    def _normalize(self, item: dict[str, Any], context: SearchContext) -> EvidenceSource:
        title = item.get("title") or "Untitled OpenWetWare result"
        snippet = compact_text(item.get("snippet") or "OpenWetWare search result.")
        evidence_type = classify_evidence(context.parsed_hypothesis, title, snippet, EvidenceType.generic_method)
        if evidence_type == EvidenceType.close_match:
            evidence_type = EvidenceType.adjacent_method
        return EvidenceSource(
            id=stable_source_id("oww", str(item.get("pageid")), title),
            source_name=self.name,
            title=title,
            url=f"https://openwetware.org/wiki/{title.replace(' ', '_')}",
            evidence_type=evidence_type,
            trust_tier=TrustTier.community_protocol,
            trust_level=TrustLevel.low,
            snippet=snippet,
            authors=[],
            year=None,
            doi=None,
            confidence=0.52 if evidence_type != EvidenceType.generic_method else 0.45,
            retrieved_at=now_utc(),
        )


class TavilyClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        if not self.settings.tavily_api_key:
            return []

        body: dict[str, Any] = {
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_usage": True,
        }
        if include_domains:
            body["include_domains"] = include_domains

        headers = {
            "Authorization": f"Bearer {self.settings.tavily_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post("https://api.tavily.com/search", json=body, headers=headers)
            response.raise_for_status()

        return response.json().get("results", [])[:max_results]

    async def extract(
        self,
        urls: list[str],
        *,
        query: str | None = None,
        chunks_per_source: int | None = None,
    ) -> list[dict[str, Any]]:
        if not self.settings.tavily_api_key or not urls:
            return []

        body: dict[str, Any] = {
            "urls": urls,
            "extract_depth": "advanced",
            "format": "markdown",
            "include_images": False,
            "include_usage": True,
        }
        if query:
            body["query"] = query
        if chunks_per_source is not None:
            body["chunks_per_source"] = chunks_per_source

        headers = {
            "Authorization": f"Bearer {self.settings.tavily_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post("https://api.tavily.com/extract", json=body, headers=headers)
            response.raise_for_status()

        payload = response.json()
        return payload.get("results", []) or payload.get("data", []) or []

    def normalize_search_result(
        self,
        item: dict[str, Any],
        context: SearchContext,
        *,
        supplier_mode: bool,
    ) -> EvidenceSource:
        title = item.get("title") or "Untitled Tavily result"
        snippet = compact_text(item.get("content") or item.get("raw_content") or "Tavily search result.")
        url = item.get("url")
        host = host_from_url(url)
        evidence_type = EvidenceType.supplier_reference if supplier_mode else classify_evidence(
            context.parsed_hypothesis,
            title,
            snippet,
            EvidenceType.generic_method,
        )
        trust_tier = TrustTier.supplier_documentation if supplier_mode else TrustTier.community_protocol
        trust_level = TrustLevel.medium if supplier_mode else TrustLevel.low
        return EvidenceSource(
            id=stable_source_id("tavily-search", url, title),
            source_name=host or "Tavily",
            title=title,
            url=url,
            evidence_type=evidence_type,
            trust_tier=trust_tier,
            trust_level=trust_level,
            snippet=snippet,
            authors=[],
            year=None,
            doi=None,
            confidence=0.63 if supplier_mode else 0.5,
            retrieved_at=now_utc(),
        )

    def normalize_extract_result(
        self,
        item: dict[str, Any],
        context: SearchContext,
        *,
        supplier_mode: bool,
        title_hint: str | None = None,
    ) -> EvidenceSource:
        url = item.get("url")
        title = item.get("title") or title_hint or host_from_url(url) or "Extracted source"
        snippet = compact_text(item.get("raw_content") or item.get("content") or item.get("markdown") or "Tavily extract result.")
        host = host_from_url(url)
        evidence_type = EvidenceType.supplier_reference if supplier_mode else classify_evidence(
            context.parsed_hypothesis,
            title,
            snippet,
            EvidenceType.generic_method,
        )
        trust_tier = TrustTier.supplier_documentation if supplier_mode else TrustTier.community_protocol
        trust_level = TrustLevel.high if supplier_mode else TrustLevel.low
        return EvidenceSource(
            id=stable_source_id("tavily-extract", url, title),
            source_name=host or "Tavily",
            title=title,
            url=url,
            evidence_type=evidence_type,
            trust_tier=trust_tier,
            trust_level=trust_level,
            snippet=snippet,
            authors=[],
            year=None,
            doi=None,
            confidence=0.71 if supplier_mode else 0.52,
            retrieved_at=now_utc(),
        )
