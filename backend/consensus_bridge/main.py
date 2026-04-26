from __future__ import annotations

import json
import os
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from mcp import ClientSession, StdioServerParameters, types as mcp_types
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings


class BridgeSearchRequest(BaseModel):
    hypothesis: str
    query: str
    domain_route: str
    literature_query_terms: list[str] = Field(default_factory=list)


class BridgeReference(BaseModel):
    title: str
    url: str | None = None
    summary: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    confidence: float | None = None


class BridgeSearchResponse(BaseModel):
    references: list[BridgeReference]
    literature_synthesis: str | None = None


class ConsensusBridge:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, request: BridgeSearchRequest) -> BridgeSearchResponse:
        try:
            result = await self._call_search_tool(request)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Consensus bridge failed: {exc}") from exc

        references = normalize_references(result)
        synthesis = normalize_synthesis(result, references)
        return BridgeSearchResponse(references=references[:5], literature_synthesis=synthesis)

    async def _call_search_tool(self, request: BridgeSearchRequest):
        server_params = StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "mcp-remote@latest",
                self.settings.consensus_mcp_server_url,
                "--transport",
                "http-only",
            ],
            env=self._child_env(),
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool = resolve_search_tool(tools.tools)
                arguments = build_tool_arguments(tool, request)
                return await session.call_tool(tool.name, arguments=arguments)

    def _child_env(self) -> dict[str, str]:
        child_env = os.environ.copy()
        bridge_home = self.settings.consensus_bridge_home
        if bridge_home:
            os.makedirs(bridge_home, exist_ok=True)
            child_env["HOME"] = bridge_home
            child_env["XDG_CONFIG_HOME"] = bridge_home
            child_env["XDG_CACHE_HOME"] = bridge_home
        return child_env


def resolve_search_tool(tools: list[Any]) -> Any:
    exact = next((tool for tool in tools if getattr(tool, "name", None) == "search"), None)
    if exact is not None:
        return exact

    fuzzy = next((tool for tool in tools if "search" in getattr(tool, "name", "").lower()), None)
    if fuzzy is not None:
        return fuzzy

    names = [getattr(tool, "name", "<unknown>") for tool in tools]
    raise RuntimeError(f"Consensus MCP search tool not found. Available tools: {names}")


def build_tool_arguments(tool: Any, request: BridgeSearchRequest) -> dict[str, Any]:
    schema = getattr(tool, "inputSchema", None) or {}
    properties = schema.get("properties") or {}
    required = schema.get("required") or []

    candidate_values: dict[str, Any] = {
        "query": request.query,
        "question": request.hypothesis,
        "hypothesis": request.hypothesis,
        "topic": request.hypothesis,
        "prompt": request.hypothesis,
        "domain_route": request.domain_route,
        "literature_query_terms": request.literature_query_terms,
        "query_terms": request.literature_query_terms,
        "keywords": request.literature_query_terms,
        "search_terms": request.literature_query_terms,
        "max_results": 5,
        "limit": 5,
        "top_k": 5,
    }

    arguments: dict[str, Any] = {}
    for key in properties:
        if key in candidate_values:
            arguments[key] = candidate_values[key]

    for key in required:
        if key in arguments:
            continue
        if key in candidate_values:
            arguments[key] = candidate_values[key]
        elif key == "query":
            arguments[key] = request.query
        elif key in {"question", "hypothesis", "topic", "prompt"}:
            arguments[key] = request.hypothesis
        elif key in {"literature_query_terms", "query_terms", "keywords", "search_terms"}:
            arguments[key] = request.literature_query_terms

    if not arguments:
        arguments["query"] = request.query

    return arguments


def normalize_references(result: Any) -> list[BridgeReference]:
    structured = getattr(result, "structuredContent", None)
    candidates = list(extract_reference_candidates(structured))
    if not candidates:
        candidates = list(extract_reference_candidates_from_text(result))

    references: list[BridgeReference] = []
    for item in candidates:
        reference = normalize_reference_item(item)
        if reference is not None:
            references.append(reference)
    return references


def normalize_reference_item(item: Any) -> BridgeReference | None:
    if not isinstance(item, dict):
        return None

    title = first_string(item, "title", "paper_title", "name", "paperTitle", "study_title")
    summary = first_string(item, "summary", "snippet", "abstract", "description", "text", "content")
    url = first_string(item, "url", "link", "paperUrl", "sourceUrl")
    doi = first_string(item, "doi", "DOI")
    year = first_int(item, "year", "publication_year", "publicationYear")
    confidence = first_float(item, "confidence", "score", "relevance")

    if not title:
        if url:
            title = url
        elif summary:
            title = summary[:120]
        else:
            return None

    authors_raw = item.get("authors") or item.get("author_names") or item.get("authorNames") or []
    authors = normalize_authors(authors_raw)
    return BridgeReference(
        title=title,
        url=url,
        summary=summary,
        authors=authors[:6],
        year=year,
        doi=doi,
        confidence=confidence,
    )


def normalize_authors(raw: Any) -> list[str]:
    if isinstance(raw, list):
        names: list[str] = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
            elif isinstance(item, dict):
                for key in ("name", "full_name", "fullName"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        names.append(value.strip())
                        break
        return names
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def extract_reference_candidates(payload: Any):
    if payload is None:
        return

    if isinstance(payload, list):
        if payload and all(isinstance(item, dict) for item in payload):
            if any(has_reference_fields(item) for item in payload):
                for item in payload:
                    yield item
                return
        for item in payload:
            yield from extract_reference_candidates(item)
        return

    if isinstance(payload, dict):
        for key in ("references", "papers", "results", "items", "sources", "studies", "evidence"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in extract_reference_candidates(value):
                    yield item
        for value in payload.values():
            if isinstance(value, (dict, list)):
                yield from extract_reference_candidates(value)


def extract_reference_candidates_from_text(result: Any):
    for content in getattr(result, "content", []) or []:
        if isinstance(content, mcp_types.TextContent):
            text = content.text.strip()
            if not text:
                continue
            parsed = parse_json_blob(text)
            if parsed is not None:
                yield from extract_reference_candidates(parsed)


def parse_json_blob(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def normalize_synthesis(result: Any, references: list[BridgeReference]) -> str | None:
    structured = getattr(result, "structuredContent", None)
    synthesis = extract_synthesis(structured)
    if synthesis:
        return synthesis

    for content in getattr(result, "content", []) or []:
        if isinstance(content, mcp_types.TextContent) and content.text.strip():
            text = content.text.strip()
            if not text.startswith("{") and len(text) > 40:
                return text[:1200]

    if references:
        joined = ", ".join(reference.title for reference in references[:3])
        return f"Consensus references for this query include: {joined}."
    return None


def extract_synthesis(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("literature_synthesis", "synthesis", "summary", "answer", "rationale"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            extracted = extract_synthesis(value)
            if extracted:
                return extracted
    elif isinstance(payload, list):
        for item in payload:
            extracted = extract_synthesis(item)
            if extracted:
                return extracted
    return None


def has_reference_fields(item: dict[str, Any]) -> bool:
    return any(key in item for key in ("title", "paper_title", "name", "url", "doi", "abstract", "summary"))


def first_string(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def first_int(item: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = item.get(key)
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


def first_float(item: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = item.get(key)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    bridge = ConsensusBridge(resolved_settings)
    app = FastAPI(title="Consensus Bridge", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        authenticated = consensus_auth_cached(resolved_settings)
        return {
            "status": "ok",
            "authenticated": authenticated,
            "detail": "Consensus OAuth cache detected" if authenticated else "Consensus OAuth not detected yet",
        }

    @app.post("/search", response_model=BridgeSearchResponse)
    async def search(request: BridgeSearchRequest) -> BridgeSearchResponse:
        return await bridge.search(request)

    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "consensus_bridge.main:app",
        host=settings.consensus_bridge_host,
        port=settings.consensus_bridge_port,
        reload=False,
    )


if __name__ == "__main__":
    main()


def consensus_auth_cached(settings: Settings) -> bool:
    homes = []
    if settings.consensus_bridge_home:
        homes.append(settings.consensus_bridge_home)
    homes.append(os.path.expanduser("~"))

    for home in homes:
        auth_dir = os.path.join(home, ".mcp-auth")
        if not os.path.isdir(auth_dir):
            continue
        for root, _, filenames in os.walk(auth_dir):
            if any(
                name.endswith(".json") or name.endswith(".sqlite") or name.endswith(".db")
                for name in filenames
            ):
                return True
    return False
