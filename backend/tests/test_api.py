from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import Settings
from app.core.database import create_db_and_tables, engine
from app.main import create_app
from app.api.routes import create_plan, list_presets
from app.models.db import Run
from app.providers.base import SearchContext
from app.services.literature_qc import LiteratureQcService
from app.services.openai_client import OpenAIStructuredClient
from app.services.plan_generation import PlanGenerationService


def build_test_app(**overrides):
    defaults = {
        "openai_api_key": "",
        "tavily_api_key": "",
        "protocols_io_token": "",
        "semantic_scholar_api_key": None,
        "consensus_mcp_enabled": False,
        "consensus_mcp_bridge_url": None,
    }
    defaults.update(overrides)
    return create_app(Settings(app_env="test", **defaults))


create_db_and_tables()


def test_presets_returns_four_hypotheses():
    payload = list_presets()
    assert len(payload) == 4
    assert any(item.id == "hela-trehalose" and item.optimized_demo for item in payload)


@pytest.mark.asyncio
async def test_hela_flow_completes_without_external_keys():
    hypothesis = (
        "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase "
        "post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard "
        "DMSO protocol, due to trehalose's superior membrane stabilization at low temperatures."
    )

    settings = Settings(app_env="test", openai_api_key="")
    parser = OpenAIStructuredClient(settings)
    parsed = await parser.parse_hypothesis(hypothesis, preset_id="hela-trehalose")
    qc = await LiteratureQcService(settings).run(
        SearchContext(parsed_hypothesis=parsed, preset_id="hela-trehalose", stage="literature_qc")
    )
    plan = (await PlanGenerationService(settings).run(parsed, qc, "hela-trehalose")).model_dump(mode="json")

    assert qc.novelty_signal == "similar_work_exists"
    assert qc.provider_trace[0].provider == "Consensus"
    assert qc.provider_trace[0].succeeded is False
    assert parsed.scientific_system == "mammalian cell cryopreservation"
    assert plan["status_label"] == "SOP draft for expert review"
    assert all(step["evidence_source_ids"] for step in plan["protocol"])
    assert plan["materials"][0]["catalog_number"] == "CCL-2"
    assert all(item["requires_procurement_check"] for item in plan["materials"])
    assert all(item["procurement_status"] == "requires_procurement_check" for item in plan["materials"][1:])
    assert all(
        item["price_status"] in {"requires_procurement_check", "contact_supplier"}
        for item in plan["budget"]["items"]
        if item["price"] is None
    )


@pytest.mark.asyncio
async def test_plan_requires_literature_qc_first():
    with Session(engine) as session:
        existing = session.get(Run, "no-qc-run")
        if existing is not None:
            session.delete(existing)
            session.commit()
        run = Run(id="no-qc-run", hypothesis="A sufficiently long hypothesis without completed QC.")
        session.add(run)
        session.commit()

        with pytest.raises(HTTPException) as excinfo:
            await create_plan("no-qc-run", session=session, settings=Settings(app_env="test"))

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == "Literature QC must complete before plan generation"


def test_allowed_origin_receives_cors_header():
    cors_app = create_app(
        Settings(
            app_env="test",
            backend_cors_allow_origins="http://localhost:5173,http://127.0.0.1:5173",
        )
    )

    client = TestClient(cors_app)
    response = client.get("/api/presets", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_regex_origin_receives_cors_header():
    cors_app = create_app(
        Settings(
            app_env="test",
            backend_cors_allow_origins="http://localhost:5173",
            backend_cors_allow_origin_regex=r"https://.*\.preview\.example\.com",
        )
    )

    client = TestClient(cors_app)
    response = client.get("/api/presets", headers={"Origin": "https://feature-123.preview.example.com"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://feature-123.preview.example.com"


def test_disallowed_origin_does_not_receive_cors_header():
    cors_app = create_app(
        Settings(
            app_env="test",
            backend_cors_allow_origins="http://localhost:5173",
        )
    )

    client = TestClient(cors_app)
    response = client.get("/api/presets", headers={"Origin": "https://evil.example.com"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_readiness_endpoint_reports_provider_statuses():
    client = TestClient(build_test_app())
    response = client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["live_ready"] is False
    assert payload["evidence_mode"] == "seeded_demo"
    assert payload["cached_live_available"] is False
    assert payload["seeded_demo_available"] is True
    provider_names = {provider["provider"] for provider in payload["providers"]}
    assert {"OpenAI", "Consensus", "Tavily", "protocols.io", "Semantic Scholar"} <= provider_names
    semantic_scholar = next(provider for provider in payload["providers"] if provider["provider"] == "Semantic Scholar")
    assert semantic_scholar["status"] == "public_mode"


async def seed_completed_run(run_id: str) -> str:
    hypothesis = (
        "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase "
        "post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard "
        "DMSO protocol, due to trehalose's superior membrane stabilization at low temperatures."
    )
    settings = Settings(app_env="test", openai_api_key="")
    parser = OpenAIStructuredClient(settings)
    parsed = await parser.parse_hypothesis(hypothesis, preset_id="hela-trehalose")
    qc = await LiteratureQcService(settings).run(
        SearchContext(parsed_hypothesis=parsed, preset_id="hela-trehalose", stage="literature_qc")
    )
    plan = await PlanGenerationService(settings).run(parsed, qc, "hela-trehalose")

    with Session(engine) as session:
        existing = session.get(Run, run_id)
        if existing is not None:
            session.delete(existing)
            session.commit()
        run = Run(
            id=run_id,
            hypothesis=hypothesis,
            preset_id="hela-trehalose",
            status="plan_complete",
            parsed_hypothesis_json=parsed.model_dump_json(),
            literature_qc_json=qc.model_dump_json(),
            plan_json=plan.model_dump_json(),
            quality_summary_json=plan.quality_summary.model_dump_json() if plan.quality_summary else None,
        )
        session.add(run)
        session.commit()

    return run_id


@pytest.mark.asyncio
async def test_runs_reviews_events_and_exports_round_trip():
    run_id = await seed_completed_run(f"completed-run-{uuid4()}")
    client = TestClient(build_test_app())

    review_response = client.post(
        f"/api/runs/{run_id}/reviews",
        json={
            "reviewer_name": "Dr. Rivera",
            "summary": "Trehalose sourcing still needs scientist confirmation.",
            "review_state": "reviewed",
            "items": [
                {
                    "target_type": "material",
                    "target_key": "Trehalose",
                    "action": "comment",
                    "comment": "Keep procurement open until supplier lot and purity are confirmed.",
                    "replacement_text": None,
                    "confidence_override": 0.62,
                }
            ],
        },
    )

    assert review_response.status_code == 200
    review_payload = review_response.json()["review"]
    assert review_payload["review_state"] == "reviewed"
    assert review_payload["items"][0]["target_key"] == "Trehalose"

    runs_response = client.get("/api/runs")
    assert runs_response.status_code == 200
    matching_run = next(item for item in runs_response.json() if item["run_id"] == run_id)
    assert matching_run["evidence_mode"] == "seeded_demo"

    events_response = client.get(f"/api/runs/{run_id}/events")
    assert events_response.status_code == 200
    assert any(event["stage"] == "review" for event in events_response.json())

    reviews_response = client.get(f"/api/runs/{run_id}/reviews")
    assert reviews_response.status_code == 200
    assert reviews_response.json()[0]["reviewer_name"] == "Dr. Rivera"

    json_export = client.get(f"/api/runs/{run_id}/export/json")
    assert json_export.status_code == 200
    assert json_export.headers["content-disposition"].endswith(f'run-{run_id}.json"')
    assert json_export.json()["review_state"] == "reviewed"

    citation_export = client.get(f"/api/runs/{run_id}/export/citations")
    assert citation_export.status_code == 200
    assert "ATCC HeLa cell line product page" in citation_export.text

    procurement_export = client.get(f"/api/runs/{run_id}/export/procurement")
    assert procurement_export.status_code == 200
    assert "requires_procurement_check" in procurement_export.text

    revised_response = client.post(f"/api/runs/{run_id}/revise")
    assert revised_response.status_code == 200
    revised_run_id = revised_response.json()["run_id"]
    assert revised_run_id != run_id
    assert revised_response.json()["plan"]["status_label"] == "Scientist-reviewed revision for expert review"

    revised_run = client.get(f"/api/runs/{revised_run_id}")
    assert revised_run.status_code == 200
    revised_payload = revised_run.json()
    assert revised_payload["review_state"] == "revised"
    assert revised_payload["parent_run_id"] == run_id
    assert revised_payload["revision_number"] == 1
    assert revised_payload["evidence_mode"] == "seeded_demo"
    trehalose_material = next(item for item in revised_payload["plan"]["materials"] if item["name"] == "Trehalose")
    assert "procurement open" in trehalose_material["notes"].lower()

    comparison_response = client.get(f"/api/runs/{revised_run_id}/comparison")
    assert comparison_response.status_code == 200
    comparison_payload = comparison_response.json()
    assert comparison_payload["baseline_run_id"] == run_id
    assert comparison_payload["current_run_id"] == revised_run_id
    assert comparison_payload["metrics"]
    assert comparison_payload["material_changes"]

    anchor_response = client.post(f"/api/runs/{revised_run_id}/presentation-anchor")
    assert anchor_response.status_code == 200
    assert anchor_response.json()["is_presentation_anchor"] is True

    pdf_export = client.get(f"/api/runs/{revised_run_id}/export/pdf")
    assert pdf_export.status_code == 200
    assert pdf_export.headers["content-type"].startswith("application/pdf")
    assert pdf_export.content.startswith(b"%PDF-1.4")
