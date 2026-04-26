from __future__ import annotations

from io import BytesIO

from app.models.schemas import ExperimentPlan, ParsedHypothesis


def build_plan_pdf(plan: ExperimentPlan, parsed: ParsedHypothesis | None = None) -> bytes:
    lines = compose_lines(plan, parsed)
    return basic_pdf(lines)


def compose_lines(plan: ExperimentPlan, parsed: ParsedHypothesis | None) -> list[str]:
    lines = [
        plan.plan_title,
        "",
        f"Status: {plan.status_label}",
        f"Generated: {plan.generated_at}",
        f"Novelty: {plan.literature_qc.novelty_signal}",
        f"QC confidence: {round(plan.literature_qc.confidence * 100)}%",
    ]
    if parsed is not None:
        lines.extend(
            [
                f"Domain: {parsed.domain}",
                f"System: {parsed.scientific_system or 'Not specified'}",
                f"Model: {parsed.model_or_organism or 'Not specified'}",
            ]
        )

    if plan.quality_summary is not None:
        lines.extend(
            [
                "",
                "Quality Summary",
                f"Operational readiness: {round(plan.quality_summary.operational_readiness * 100)}%",
                f"Evidence completeness: {round(plan.quality_summary.evidence_completeness * 100)}%",
                f"Review burden: {round(plan.quality_summary.review_burden * 100)}%",
            ]
        )

    lines.extend(
        [
            "",
            "Overview",
            plan.overview.summary,
            *[f"- {bullet}" for bullet in plan.overview.bullets],
            "",
            "Study Design",
            plan.study_design.summary,
            *[f"- {bullet}" for bullet in plan.study_design.bullets],
            "",
            "Protocol",
        ]
    )
    for step in plan.protocol:
        lines.append(f"{step.step_number}. {step.title}")
        lines.append(step.purpose)
        lines.extend(f"  - {action}" for action in step.actions)
        if step.review_reason:
            lines.append(f"  Review note: {step.review_reason}")

    lines.extend(["", "Materials"])
    for item in plan.materials:
        lines.append(
            f"- {item.name} | {item.vendor or 'unknown vendor'} | catalog: {item.catalog_number or 'null'} | procurement: {item.procurement_status}"
        )

    lines.extend(["", "Budget"])
    for item in plan.budget.items:
        lines.append(
            f"- {item.name} | price: {item.price or 'null'} | price status: {item.price_status}"
        )

    lines.extend(["", "Timeline", plan.timeline.summary, *[f"- {bullet}" for bullet in plan.timeline.bullets]])
    lines.extend(["", "Validation", plan.validation.summary, *[f"- {bullet}" for bullet in plan.validation.bullets]])
    lines.extend(["", "Risks", plan.risks.summary, *[f"- {bullet}" for bullet in plan.risks.bullets]])
    lines.extend(["", "Sources"])
    for source in plan.sources[:20]:
        lines.append(f"- {source.title} | {source.source_name} | {source.url or 'URL not available'}")

    return lines


def basic_pdf(lines: list[str]) -> bytes:
    page_width = 612
    page_height = 792
    left_margin = 48
    top_margin = 740
    line_height = 14
    max_lines = 46

    pages = [lines[index : index + max_lines] for index in range(0, len(lines), max_lines)] or [[]]
    objects: list[bytes] = []

    font_object_number = 3 + (len(pages) * 2)
    kids = []
    page_object_numbers = []
    for index, page_lines in enumerate(pages):
        page_object_number = 3 + (index * 2)
        content_object_number = 4 + (index * 2)
        page_object_numbers.append(page_object_number)
        kids.append(f"{page_object_number} 0 R")
        objects.append(
            (
                f"{page_object_number} 0 obj\n"
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 {font_object_number} 0 R >> >> "
                f"/Contents {content_object_number} 0 R >>\nendobj\n"
            ).encode()
        )

        stream = page_stream(page_lines, left_margin, top_margin, line_height)
        objects.append(
            (
                f"{content_object_number} 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode()
                + stream
                + b"\nendstream\nendobj\n"
            )
        )

    objects.insert(0, b"2 0 obj\n<< /Type /Pages /Count " + str(len(pages)).encode() + b" /Kids [" + " ".join(kids).encode() + b"] >>\nendobj\n")
    objects.insert(0, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(f"{font_object_number} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode())

    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(buffer.tell())
        buffer.write(obj)

    xref_start = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode())
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode())
    buffer.write(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode()
    )
    return buffer.getvalue()


def page_stream(lines: list[str], x: int, y: int, line_height: int) -> bytes:
    commands = ["BT", "/F1 11 Tf"]
    current_y = y
    for line in lines:
        safe = escape_pdf_text(line[:140])
        commands.append(f"1 0 0 1 {x} {current_y} Tm ({safe}) Tj")
        current_y -= line_height
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
