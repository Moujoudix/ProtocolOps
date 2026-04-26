import pytest

from app.core.config import Settings
from app.providers import protocols as protocols_module


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"results": [{"url": "https://www.sigmaaldrich.com/US/en/search/trehalose", "title": "Trehalose"}]}


class _FakeAsyncClient:
    def __init__(self, *, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers):
        _FakeAsyncClient.last_request = {
            "url": url,
            "json": json,
            "headers": headers,
        }
        return _FakeResponse()


@pytest.mark.asyncio
async def test_tavily_search_uses_boolean_include_answer(monkeypatch):
    monkeypatch.setattr(protocols_module.httpx, "AsyncClient", _FakeAsyncClient)
    client = protocols_module.TavilyClient(Settings(tavily_api_key="test-key"))

    results = await client.search(
        "Sigma trehalose product page",
        include_domains=["sigmaaldrich.com", "sigma-aldrich.com"],
        max_results=5,
    )

    assert results[0]["url"] == "https://www.sigmaaldrich.com/US/en/search/trehalose"
    assert _FakeAsyncClient.last_request["json"]["include_answer"] is False
