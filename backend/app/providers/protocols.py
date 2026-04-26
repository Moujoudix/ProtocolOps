from typing import Any

import httpx

from app.core.config import Settings
from app.models.schemas import EvidenceSource, EvidenceType, now_utc
from app.providers.base import SearchContext
from app.providers.utils import compact_text, host_from_url, stable_source_id


class ProtocolsIoProvider:
    name = "protocols.io"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, context: SearchContext) -> list[EvidenceSource]:
        if not self.settings.protocols_io_token:
            return []

        url = "https://www.protocols.io/api/v3/protocols"
        params = {
            "filter": "public",
            "key": query,
            "order_field": "relevance",
            "order_dir": "desc",
            "page_size": 3,
        }
        headers = {"Authorization": f"Bearer {self.settings.protocols_io_token}"}
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError:
            return []

        payload = response.json()
        return [self._normalize(item) for item in payload.get("items", [])[:3]]

    def _normalize(self, item: dict[str, Any]) -> EvidenceSource:
        uri = item.get("uri")
        url = item.get("url") or (f"https://www.protocols.io/view/{uri}" if uri else None)
        return EvidenceSource(
            id=stable_source_id("pio", str(item.get("id")), uri, item.get("title")),
            source_name=self.name,
            title=item.get("title") or "Untitled protocols.io result",
            url=url,
            evidence_type=EvidenceType.generic_protocol_evidence,
            snippet=compact_text(item.get("description") or item.get("materials_text") or "Public protocol metadata result."),
            authors=[],
            year=None,
            doi=item.get("doi"),
            confidence=0.62,
            retrieved_at=now_utc(),
        )


class OpenWetWareProvider:
    name = "OpenWetWare"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, context: SearchContext) -> list[EvidenceSource]:
        url = "https://openwetware.org/wiki/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 3,
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
        except httpx.HTTPError:
            return []

        payload = response.json()
        return [self._normalize(item) for item in payload.get("query", {}).get("search", [])[:3]]

    def _normalize(self, item: dict[str, Any]) -> EvidenceSource:
        title = item.get("title") or "Untitled OpenWetWare result"
        return EvidenceSource(
            id=stable_source_id("oww", str(item.get("pageid")), title),
            source_name=self.name,
            title=title,
            url=f"https://openwetware.org/wiki/{title.replace(' ', '_')}",
            evidence_type=EvidenceType.generic_protocol_evidence,
            snippet=compact_text(item.get("snippet") or "OpenWetWare search result."),
            authors=[],
            year=None,
            doi=None,
            confidence=0.5,
            retrieved_at=now_utc(),
        )


class TavilyProvider:
    name = "Tavily"

    def __init__(self, settings: Settings, include_domains: list[str] | None = None, source_name: str | None = None):
        self.settings = settings
        self.include_domains = include_domains
        if source_name:
            self.name = source_name

    async def search(self, query: str, context: SearchContext) -> list[EvidenceSource]:
        if not self.settings.tavily_api_key:
            return []

        body: dict[str, Any] = {
            "query": query,
            "search_depth": "basic",
            "max_results": 4 if self.include_domains else 3,
            "include_answer": False,
            "include_raw_content": False,
        }
        if self.include_domains:
            body["include_domains"] = self.include_domains

        headers = {
            "Authorization": f"Bearer {self.settings.tavily_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.post("https://api.tavily.com/search", json=body, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError:
            return []

        payload = response.json()
        return [self._normalize(item) for item in payload.get("results", [])[:4]]

    def _normalize(self, item: dict[str, Any]) -> EvidenceSource:
        url = item.get("url")
        host = host_from_url(url)
        evidence_type = EvidenceType.supplier_evidence if self.include_domains else EvidenceType.generic_protocol_evidence
        return EvidenceSource(
            id=stable_source_id("tavily", url, item.get("title")),
            source_name=host or self.name,
            title=item.get("title") or "Untitled Tavily result",
            url=url,
            evidence_type=evidence_type,
            snippet=compact_text(item.get("content") or "Tavily search result."),
            authors=[],
            year=None,
            doi=None,
            confidence=0.56 if evidence_type == EvidenceType.supplier_evidence else 0.5,
            retrieved_at=now_utc(),
        )

