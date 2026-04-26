from hashlib import sha1
from urllib.parse import urlparse

from app.models.schemas import EvidenceType, ParsedHypothesis


def stable_source_id(prefix: str, *parts: str | None) -> str:
    material = "|".join(part or "" for part in parts)
    digest = sha1(material.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def compact_text(value: str | None, limit: int = 600) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def host_from_url(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).netloc
    return host or None


def classify_evidence(parsed: ParsedHypothesis, title: str, snippet: str, default: EvidenceType) -> EvidenceType:
    haystack = f"{title} {snippet}".lower()
    required = [
        parsed.organism_or_system,
        parsed.intervention,
        parsed.comparator,
        parsed.outcome,
    ]
    matches = sum(1 for item in required if item and any(token in haystack for token in item.lower().split()[:3]))
    if matches >= 3:
        return EvidenceType.exact_evidence
    if matches >= 1:
        return EvidenceType.adjacent_evidence
    return default

