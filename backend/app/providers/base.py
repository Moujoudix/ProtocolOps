from dataclasses import dataclass
from typing import Protocol

from app.models.schemas import EvidenceSource, ParsedHypothesis


@dataclass(frozen=True)
class SearchContext:
    parsed_hypothesis: ParsedHypothesis
    preset_id: str | None
    stage: str


class SourceProvider(Protocol):
    name: str

    async def search(self, query: str, context: SearchContext) -> list[EvidenceSource]:
        ...

