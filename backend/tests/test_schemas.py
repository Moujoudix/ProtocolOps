import pytest
from pydantic import ValidationError

from app.models.schemas import MaterialItem, PriceStatus, ProcurementStatus, ProtocolStep


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
    assert material.procurement_status == ProcurementStatus.requires_procurement_check
    assert material.price_status == PriceStatus.contact_supplier


def test_material_without_vendor_or_price_uses_procurement_check_status():
    material = MaterialItem(
        name="Unknown buffer",
        role="Support material",
        vendor=None,
        catalog_number=None,
        price=None,
        currency=None,
        evidence_source_ids=["assumption-source"],
        notes="Unspecified support material.",
        confidence=0.2,
    )

    assert material.procurement_status == ProcurementStatus.requires_procurement_check
    assert material.price_status == PriceStatus.requires_procurement_check


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
