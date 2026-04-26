from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import Settings
from app.core.database import engine
from app.main import app, create_app
from app.models.db import Run


def test_presets_returns_four_hypotheses():
    with TestClient(app) as client:
        response = client.get("/api/presets")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 4
    assert any(item["id"] == "hela-trehalose" and item["optimized_demo"] for item in payload)


def test_hela_flow_completes_without_external_keys():
    hypothesis = (
        "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase "
        "post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard "
        "DMSO protocol, due to trehalose's superior membrane stabilization at low temperatures."
    )

    with TestClient(app) as client:
        qc_response = client.post(
            "/api/literature-qc",
            json={"hypothesis": hypothesis, "preset_id": "hela-trehalose"},
        )
        assert qc_response.status_code == 200
        qc_payload = qc_response.json()
        assert qc_payload["literature_qc"]["novelty_signal"] == "similar_work_exists"

        plan_response = client.post(f"/api/runs/{qc_payload['run_id']}/plan")

    assert plan_response.status_code == 200
    plan = plan_response.json()["plan"]
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


def test_plan_requires_literature_qc_first():
    with TestClient(app):
        with Session(engine) as session:
            run = Run(id="no-qc-run", hypothesis="A sufficiently long hypothesis without completed QC.")
            session.add(run)
            session.commit()

        with TestClient(app) as client:
            response = client.post("/api/runs/no-qc-run/plan")

    assert response.status_code == 409
    assert response.json()["detail"] == "Literature QC must complete before plan generation"


def test_allowed_origin_receives_cors_header():
    cors_app = create_app(
        Settings(
            backend_cors_allow_origins="http://localhost:5173,http://127.0.0.1:5173",
        )
    )

    with TestClient(cors_app) as client:
        response = client.get("/api/presets", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_regex_origin_receives_cors_header():
    cors_app = create_app(
        Settings(
            backend_cors_allow_origins="http://localhost:5173",
            backend_cors_allow_origin_regex=r"https://.*\.preview\.example\.com",
        )
    )

    with TestClient(cors_app) as client:
        response = client.get("/api/presets", headers={"Origin": "https://feature-123.preview.example.com"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://feature-123.preview.example.com"


def test_disallowed_origin_does_not_receive_cors_header():
    cors_app = create_app(
        Settings(
            backend_cors_allow_origins="http://localhost:5173",
        )
    )

    with TestClient(cors_app) as client:
        response = client.get("/api/presets", headers={"Origin": "https://evil.example.com"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
