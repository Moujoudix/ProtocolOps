from __future__ import annotations

from app.models.schemas import ComparisonMetricRecord, ExperimentPlan, RunComparisonResponse


def compare_plans(
    *,
    baseline_run_id: str,
    current_run_id: str,
    baseline: ExperimentPlan,
    current: ExperimentPlan,
) -> RunComparisonResponse:
    metrics = [
        metric("Operational readiness", baseline.quality_summary.operational_readiness if baseline.quality_summary else None, current.quality_summary.operational_readiness if current.quality_summary else None),
        metric("Literature confidence", baseline.quality_summary.literature_confidence if baseline.quality_summary else None, current.quality_summary.literature_confidence if current.quality_summary else None),
        metric("Protocol confidence", baseline.quality_summary.protocol_confidence if baseline.quality_summary else None, current.quality_summary.protocol_confidence if current.quality_summary else None),
        metric("Materials confidence", baseline.quality_summary.materials_confidence if baseline.quality_summary else None, current.quality_summary.materials_confidence if current.quality_summary else None),
        metric("Budget confidence", baseline.quality_summary.budget_confidence if baseline.quality_summary else None, current.quality_summary.budget_confidence if current.quality_summary else None),
        metric("Review burden", baseline.quality_summary.review_burden if baseline.quality_summary else None, current.quality_summary.review_burden if current.quality_summary else None),
    ]

    protocol_changes = compare_protocol(baseline, current)
    material_changes = compare_materials(baseline, current)
    budget_changes = compare_budget(baseline, current)
    summary = build_summary(metrics, protocol_changes, material_changes, budget_changes)

    return RunComparisonResponse(
        baseline_run_id=baseline_run_id,
        current_run_id=current_run_id,
        baseline_title=baseline.plan_title,
        current_title=current.plan_title,
        summary=summary,
        metrics=metrics,
        protocol_changes=protocol_changes,
        material_changes=material_changes,
        budget_changes=budget_changes,
    )


def metric(label: str, baseline: float | None, current: float | None) -> ComparisonMetricRecord:
    if baseline is None or current is None:
        return ComparisonMetricRecord(label=label, baseline="n/a", current="n/a", delta=None)
    return ComparisonMetricRecord(
        label=label,
        baseline=f"{round(baseline * 100)}%",
        current=f"{round(current * 100)}%",
        delta=round(current - baseline, 4),
    )


def compare_protocol(baseline: ExperimentPlan, current: ExperimentPlan) -> list[str]:
    changes: list[str] = []
    for index, step in enumerate(current.protocol):
        if index >= len(baseline.protocol):
            changes.append(f"Added protocol step {step.step_number}: {step.title}.")
            continue
        previous = baseline.protocol[index]
        if previous.title != step.title:
            changes.append(f"Protocol step {step.step_number} title changed from '{previous.title}' to '{step.title}'.")
        if previous.review_reason != step.review_reason and step.review_reason:
            changes.append(f"Protocol step {step.step_number} review note changed: {step.review_reason}")
        if previous.confidence != step.confidence:
            changes.append(
                f"Protocol step {step.step_number} confidence moved from {round(previous.confidence * 100)}% to {round(step.confidence * 100)}%."
            )
    return changes[:8]


def compare_materials(baseline: ExperimentPlan, current: ExperimentPlan) -> list[str]:
    changes: list[str] = []
    baseline_by_name = {item.name: item for item in baseline.materials}
    current_names = {item.name for item in current.materials}
    for item in current.materials:
        previous = baseline_by_name.get(item.name)
        if previous is None:
            changes.append(f"Added material: {item.name}.")
            continue
        if previous.vendor != item.vendor or previous.catalog_number != item.catalog_number:
            changes.append(
                f"Material '{item.name}' sourcing changed from {previous.vendor or 'unknown'} / {previous.catalog_number or 'null'} to {item.vendor or 'unknown'} / {item.catalog_number or 'null'}."
            )
        if previous.requires_procurement_check != item.requires_procurement_check:
            changes.append(
                f"Material '{item.name}' procurement status changed to {'requires review' if item.requires_procurement_check else 'source-backed'}."
            )
        if previous.notes != item.notes:
            changes.append(f"Material note changed for '{item.name}'.")

    for previous in baseline.materials:
        if previous.name not in current_names:
            changes.append(f"Removed material: {previous.name}.")
    return changes[:8]


def compare_budget(baseline: ExperimentPlan, current: ExperimentPlan) -> list[str]:
    changes: list[str] = []
    if len(baseline.budget.items) != len(current.budget.items):
        changes.append(
            f"Budget line count changed from {len(baseline.budget.items)} to {len(current.budget.items)}."
        )

    baseline_by_name = {item.name: item for item in baseline.budget.items}
    for item in current.budget.items:
        previous = baseline_by_name.get(item.name)
        if previous is None:
            changes.append(f"Added budget line: {item.name}.")
            continue
        if previous.price_status != item.price_status:
            changes.append(f"Budget line '{item.name}' price status changed to {item.price_status}.")
        if previous.notes != item.notes:
            changes.append(f"Budget note changed for '{item.name}'.")
    return changes[:8]


def build_summary(
    metrics: list[ComparisonMetricRecord],
    protocol_changes: list[str],
    material_changes: list[str],
    budget_changes: list[str],
) -> list[str]:
    summary: list[str] = []
    readiness = next((item for item in metrics if item.label == "Operational readiness"), None)
    if readiness and readiness.delta is not None:
        direction = "improved" if readiness.delta >= 0 else "decreased"
        summary.append(f"Operational readiness {direction} by {abs(round(readiness.delta * 100))} percentage points.")

    review_burden = next((item for item in metrics if item.label == "Review burden"), None)
    if review_burden and review_burden.delta is not None:
        direction = "increased" if review_burden.delta > 0 else "decreased"
        summary.append(f"Review burden {direction} by {abs(round(review_burden.delta * 100))} percentage points.")

    if protocol_changes:
        summary.append(f"{len(protocol_changes)} protocol change(s) were introduced after review.")
    if material_changes:
        summary.append(f"{len(material_changes)} material or sourcing change(s) were introduced after review.")
    if budget_changes:
        summary.append(f"{len(budget_changes)} budget change(s) were introduced after review.")
    return summary[:6]
