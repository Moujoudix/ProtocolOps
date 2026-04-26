from __future__ import annotations

from typing import Any
from xml.etree import ElementTree

import httpx

from app.core.config import Settings
from app.models.schemas import EvidenceSource, EvidenceType, TrustLevel, TrustTier, now_utc
from app.providers.base import ProviderSearchResult, SearchContext
from app.providers.utils import classify_evidence, compact_text, stable_source_id


class SemanticScholarProvider:
    name = "Semantic Scholar"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, context: SearchContext) -> ProviderSearchResult:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": 5,
            "fields": (
                "title,url,abstract,year,authors,externalIds,venue,publicationDate,"
                "citationCount,openAccessPdf,publicationTypes"
            ),
        }
        headers = {}
        if self.settings.semantic_scholar_api_key:
            headers["x-api-key"] = self.settings.semantic_scholar_api_key

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

        payload = response.json()
        sources = [self._normalize(item, context) for item in payload.get("data", [])[:5]]
        return ProviderSearchResult(sources=sources)

    def _normalize(self, item: dict[str, Any], context: SearchContext) -> EvidenceSource:
        title = item.get("title") or "Untitled Semantic Scholar result"
        snippet = compact_text(item.get("abstract") or item.get("venue") or "No abstract returned by provider.")
        external_ids = item.get("externalIds") or {}
        authors = [author.get("name", "") for author in item.get("authors", []) if author.get("name")]
        evidence_type = classify_evidence(context.parsed_hypothesis, title, snippet, EvidenceType.close_match)
        return EvidenceSource(
            id=stable_source_id("s2", item.get("paperId"), title),
            source_name=self.name,
            title=title,
            url=item.get("url"),
            evidence_type=evidence_type,
            trust_tier=TrustTier.literature_database,
            trust_level=TrustLevel.high if evidence_type == EvidenceType.exact_match else TrustLevel.medium,
            snippet=snippet,
            authors=authors[:6],
            year=item.get("year"),
            doi=external_ids.get("DOI"),
            confidence=_confidence_for_evidence(evidence_type, exact=0.8, close=0.67, adjacent=0.58, generic=0.48),
            retrieved_at=now_utc(),
        )


class EuropePmcProvider:
    name = "Europe PMC"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, context: SearchContext) -> ProviderSearchResult:
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": 5,
        }
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        payload = response.json()
        results = payload.get("resultList", {}).get("result", [])
        sources = [self._normalize(item, context) for item in results[:5]]
        return ProviderSearchResult(sources=sources)

    def _normalize(self, item: dict[str, Any], context: SearchContext) -> EvidenceSource:
        title = item.get("title") or "Untitled Europe PMC result"
        snippet = compact_text(item.get("abstractText") or item.get("journalTitle") or "No abstract returned by provider.")
        doi = item.get("doi")
        url = f"https://europepmc.org/article/{item.get('source')}/{item.get('id')}" if item.get("source") and item.get("id") else None
        evidence_type = classify_evidence(context.parsed_hypothesis, title, snippet, EvidenceType.close_match)
        return EvidenceSource(
            id=stable_source_id("epmc", item.get("source"), item.get("id"), title),
            source_name=self.name,
            title=title,
            url=url,
            evidence_type=evidence_type,
            trust_tier=TrustTier.literature_database,
            trust_level=TrustLevel.high if evidence_type in {EvidenceType.exact_match, EvidenceType.close_match} else TrustLevel.medium,
            snippet=snippet,
            authors=[name.strip() for name in (item.get("authorString") or "").split(",") if name.strip()][:6],
            year=_safe_int(item.get("pubYear")),
            doi=doi,
            confidence=_confidence_for_evidence(evidence_type, exact=0.79, close=0.66, adjacent=0.57, generic=0.48),
            retrieved_at=now_utc(),
        )


class NcbiEutilsProvider:
    name = "NCBI E-utilities"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, context: SearchContext) -> ProviderSearchResult:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            search_response = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params={"db": "pubmed", "term": query, "retmode": "json", "retmax": 5},
            )
            search_response.raise_for_status()
            ids = search_response.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return ProviderSearchResult(sources=[])

            summary_response = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
            )
            summary_response.raise_for_status()

        payload = summary_response.json()
        result_map = payload.get("result", {})
        sources = []
        for pmid in ids:
            item = result_map.get(pmid)
            if not item:
                continue
            title = item.get("title") or "Untitled PubMed result"
            snippet = compact_text(item.get("source") or item.get("fulljournalname") or "PubMed metadata result.")
            evidence_type = classify_evidence(context.parsed_hypothesis, title, snippet, EvidenceType.close_match)
            sources.append(
                EvidenceSource(
                    id=stable_source_id("pmid", pmid, title),
                    source_name=self.name,
                    title=title,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    evidence_type=evidence_type,
                    trust_tier=TrustTier.literature_database,
                    trust_level=TrustLevel.medium,
                    snippet=snippet,
                    authors=[author.get("name", "") for author in item.get("authors", []) if author.get("name")][:6],
                    year=_safe_pubdate_year(item.get("pubdate")),
                    doi=None,
                    confidence=_confidence_for_evidence(evidence_type, exact=0.73, close=0.61, adjacent=0.53, generic=0.45),
                    retrieved_at=now_utc(),
                )
            )
        return ProviderSearchResult(sources=sources)


class ArxivProvider:
    name = "arXiv"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, context: SearchContext) -> ProviderSearchResult:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(
                "https://export.arxiv.org/api/query",
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": 5,
                },
            )
            response.raise_for_status()

        root = ElementTree.fromstring(response.text)
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        sources: list[EvidenceSource] = []
        for entry in root.findall("atom:entry", namespace)[:5]:
            title = compact_text(entry.findtext("atom:title", default="", namespaces=namespace) or "Untitled arXiv result", limit=240)
            summary = compact_text(entry.findtext("atom:summary", default="", namespaces=namespace) or "No summary returned by provider.")
            url = entry.findtext("atom:id", default=None, namespaces=namespace)
            evidence_type = classify_evidence(context.parsed_hypothesis, title, summary, EvidenceType.adjacent_method)
            sources.append(
                EvidenceSource(
                    id=stable_source_id("arxiv", url, title),
                    source_name=self.name,
                    title=title,
                    url=url,
                    evidence_type=evidence_type,
                    trust_tier=TrustTier.literature_database,
                    trust_level=TrustLevel.medium,
                    snippet=summary,
                    authors=[
                        compact_text(author.findtext("atom:name", default="", namespaces=namespace), limit=120)
                        for author in entry.findall("atom:author", namespace)
                        if author.findtext("atom:name", default="", namespaces=namespace)
                    ][:6],
                    year=_safe_pubdate_year(entry.findtext("atom:published", default=None, namespaces=namespace)),
                    doi=None,
                    confidence=_confidence_for_evidence(evidence_type, exact=0.69, close=0.59, adjacent=0.52, generic=0.44),
                    retrieved_at=now_utc(),
                )
            )
        return ProviderSearchResult(sources=sources)


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_pubdate_year(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value[:4])
    except (TypeError, ValueError):
        return None


def _confidence_for_evidence(
    evidence_type: EvidenceType,
    *,
    exact: float,
    close: float,
    adjacent: float,
    generic: float,
) -> float:
    if evidence_type == EvidenceType.exact_match:
        return exact
    if evidence_type == EvidenceType.close_match:
        return close
    if evidence_type == EvidenceType.adjacent_method:
        return adjacent
    return generic
