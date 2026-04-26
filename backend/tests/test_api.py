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
    return create_app(Settings(app_env="test", **overrides))


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
    assert qc.provider_trace == []
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
