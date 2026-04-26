import os
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


HELA_HYPOTHESIS = (
    "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase "
    "post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard "
    "DMSO protocol, due to trehalose's superior membrane stabilization at low temperatures."
)


def live_enabled() -> bool:
    return os.getenv("RUN_LIVE_INTEGRATION", "").lower() in {"1", "true", "yes"}


def require_live_env(*extra_keys: str) -> None:
    if not live_enabled():
        pytest.skip("Set RUN_LIVE_INTEGRATION=1 to run live integration tests.")

    required = ["OPENAI_API_KEY", "TAVILY_API_KEY", "PROTOCOLS_IO_TOKEN", *extra_keys]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        pytest.skip(f"Missing live integration env vars: {', '.join(missing)}")


def build_live_settings(*, consensus_enabled: bool, consensus_bridge_url: str | None = None) -> Settings:
    return Settings(
        app_env="development",
        openai_api_key=os.environ["OPENAI_API_KEY"],
        openai_parse_model=os.getenv("OPENAI_PARSE_MODEL", "gpt-5.4-mini"),
        openai_plan_model=os.getenv("OPENAI_PLAN_MODEL", "gpt-5.5"),
        openai_fallback_model=os.getenv("OPENAI_FALLBACK_MODEL", "gpt-5.4-mini"),
        tavily_api_key=os.environ["TAVILY_API_KEY"],
        protocols_io_token=os.environ["PROTOCOLS_IO_TOKEN"],
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None,
        consensus_mcp_enabled=consensus_enabled,
        consensus_mcp_bridge_url=consensus_bridge_url or os.getenv("CONSENSUS_MCP_BRIDGE_URL"),
        request_timeout_seconds=30.0,
    )


def test_live_hela_end_to_end_with_real_providers():
    require_live_env("CONSENSUS_MCP_BRIDGE_URL")
    app = create_app(build_live_settings(consensus_enabled=True))
    client = TestClient(app)

    qc_response = client.post(
        "/api/literature-qc",
        json={"hypothesis": HELA_HYPOTHESIS, "preset_id": "hela-trehalose"},
    )
    assert qc_response.status_code == 200, qc_response.text
    qc_payload = qc_response.json()
    run_id = qc_payload["run_id"]
    literature_qc = qc_payload["literature_qc"]
    provider_trace = literature_qc["provider_trace"]

    assert [entry["provider"] for entry in provider_trace[:3]] == [
        "Consensus",
        "Semantic Scholar",
        "Europe PMC",
    ]
    assert provider_trace[0]["succeeded"] is True
    assert not any(source["id"].startswith("seed-") for source in literature_qc["literature_sources"])

    plan_response = client.post(f"/api/runs/{run_id}/plan")
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()["plan"]

    assert all(step["evidence_source_ids"] for step in plan["protocol"])
    assert not any(source["id"].startswith("seed-") for source in plan["sources"])
    assert any(source["source_name"] == "Consensus" for source in plan["sources"])

    supplier_hosts = {
        urlparse(source["url"]).netloc
        for source in plan["sources"]
        if source.get("url")
    }
    assert any("atcc.org" in host for host in supplier_hosts)
    assert any("thermofisher.com" in host for host in supplier_hosts)
    assert any("promega.com" in host for host in supplier_hosts)
    assert any("sigmaaldrich.com" in host or "sigma-aldrich.com" in host for host in supplier_hosts)

    for item in plan["materials"]:
        if item["catalog_number"] is None:
            assert item["procurement_status"] == "requires_procurement_check"
    for item in plan["budget"]["items"]:
        if item["price"] is None:
            assert item["price_status"] in {"requires_procurement_check", "contact_supplier"}


def test_live_hela_qc_recovers_when_consensus_bridge_is_unavailable():
    require_live_env()
    app = create_app(
        build_live_settings(
            consensus_enabled=True,
            consensus_bridge_url="http://127.0.0.1:9/search",
        )
    )
    client = TestClient(app)

    qc_response = client.post(
        "/api/literature-qc",
        json={"hypothesis": HELA_HYPOTHESIS, "preset_id": "hela-trehalose"},
    )
    assert qc_response.status_code == 200, qc_response.text
    literature_qc = qc_response.json()["literature_qc"]
    provider_trace = literature_qc["provider_trace"]

    assert provider_trace[0]["provider"] == "Consensus"
    assert provider_trace[0]["succeeded"] is False
    assert [entry["provider"] for entry in provider_trace[1:3]] == [
        "Semantic Scholar",
        "Europe PMC",
    ]
    assert any(source["source_name"] in {"Semantic Scholar", "Europe PMC"} for source in literature_qc["literature_sources"])
