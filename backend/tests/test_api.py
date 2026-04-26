from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import engine
from app.main import app
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
    assert plan["protocol"][0]["evidence_source_ids"]
    assert all(item["catalog_number"] is None for item in plan["materials"])
    assert all(item["requires_procurement_check"] for item in plan["materials"])


def test_plan_requires_literature_qc_first():
    with TestClient(app):
        with Session(engine) as session:
            run = Run(id="no-qc-run", hypothesis="A sufficiently long hypothesis without completed QC.")
            session.add(run)
            session.commit()

        with TestClient(app) as client:
            response = client.post("/api/runs/no-qc-run/plan")

    assert response.status_code == 409

