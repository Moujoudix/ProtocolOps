from app.core.config import Settings
from app.models.schemas import DomainRoute
from app.providers.base import SourceProvider
from app.providers.literature import EuropePmcProvider, SemanticScholarProvider
from app.providers.protocols import OpenWetWareProvider, ProtocolsIoProvider, TavilyProvider


SUPPLIER_DOMAINS = [
    "atcc.org",
    "thermofisher.com",
    "promega.com",
    "sigmaaldrich.com",
    "sigma-aldrich.com",
]


class SourceRouter:
    def __init__(self, settings: Settings):
        literature = [SemanticScholarProvider(settings), EuropePmcProvider(settings)]
        evidence_common = [
            ProtocolsIoProvider(settings),
            OpenWetWareProvider(settings),
            TavilyProvider(settings),
        ]
        supplier_search = TavilyProvider(settings, include_domains=SUPPLIER_DOMAINS, source_name="Supplier search")

        self._literature_routes: dict[DomainRoute, list[SourceProvider]] = {
            DomainRoute.cell_biology: literature,
            DomainRoute.diagnostics_biosensor: literature,
            DomainRoute.animal_gut_health: literature,
            DomainRoute.microbial_electrochemistry: literature,
        }
        self._evidence_routes: dict[DomainRoute, list[SourceProvider]] = {
            DomainRoute.cell_biology: [*evidence_common, supplier_search],
            DomainRoute.diagnostics_biosensor: evidence_common,
            DomainRoute.animal_gut_health: evidence_common,
            DomainRoute.microbial_electrochemistry: evidence_common,
        }

    def literature_providers(self, domain_route: DomainRoute) -> list[SourceProvider]:
        return list(self._literature_routes[domain_route])

    def evidence_pack_providers(self, domain_route: DomainRoute) -> list[SourceProvider]:
        return list(self._evidence_routes[domain_route])

