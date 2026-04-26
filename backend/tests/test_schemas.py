import pytest
from pydantic import ValidationError

from app.models.schemas import MaterialItem, ProtocolStep


def test_material_missing_catalog_or_price_requires_procurement_check():
    material = MaterialItem(
        name="Trehalose",
        role="Candidate cryoprotectant",
        vendor="Supplier",
        catalog_number=None,
        price=None,
        currency=None,
        requires_procurement_check=False,
        evidence_source_ids=["seed-sigma-trehalose"],
        notes="Procurement details must be checked.",
        confidence=0.5,
    )

    assert material.requires_procurement_check is True


def test_protocol_steps_require_evidence_source_ids():
    with pytest.raises(ValidationError):
        ProtocolStep(
            step_number=1,
            title="Unsupported step",
            purpose="Should fail validation",
            actions=["Do something"],
            critical_parameters=[],
            materials=[],
            evidence_source_ids=[],
            confidence=0.5,
            expert_review_required=True,
            review_reason=None,
        )

