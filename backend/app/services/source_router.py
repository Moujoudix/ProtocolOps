from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.models.schemas import DomainRoute
from app.providers.literature import ArxivProvider, EuropePmcProvider, NcbiEutilsProvider, SemanticScholarProvider
from app.providers.protocols import OpenWetWareProvider, ProtocolsIoProvider


SUPPLIER_DOMAINS = [
    "atcc.org",
    "thermofisher.com",
    "promega.com",
    "sigmaaldrich.com",
    "sigma-aldrich.com",
    "abcam.com",
    "bio-techne.com",
]


PROTOCOL_QUERY_PACKS: dict[DomainRoute, list[str]] = {
    DomainRoute.cell_biology: [
        "cell freezing",
        "cryopreservation",
        "DMSO cell freezing",
        "adherent cell cryopreservation",
        "cell thawing",
        "post-thaw viability",
        "cell viability assay",
    ],
    DomainRoute.diagnostics_biosensor: [
        "electrochemical biosensor",
        "biosensor",
        "paper-based sensor",
        "immunoassay",
        "antibody functionalization",
        "C-reactive protein",
        "CRP assay",
    ],
    DomainRoute.animal_gut_health: [
        "FITC-dextran permeability assay",
        "gut permeability mouse",
        "Lactobacillus culture",
        "intestinal permeability",
        "tight junction protein assay",
    ],
    DomainRoute.microbial_electrochemistry: [
        "bioelectrochemical protocol",
        "microbial electrosynthesis",
        "anaerobic culture",
        "acetate quantification",
        "CO2 fixation reactor",
    ],
}


LITERATURE_QUERY_EXAMPLES: dict[DomainRoute, list[str]] = {
    DomainRoute.cell_biology: [
        "trehalose HeLa cryopreservation viability DMSO",
        "trehalose mammalian cell cryopreservation post-thaw viability",
        "HeLa cryopreservation DMSO post-thaw viability",
        "trehalose cryoprotectant post-thaw viability mammalian cells",
    ],
    DomainRoute.diagnostics_biosensor: [
        "CRP electrochemical biosensor anti-CRP antibody whole blood",
        "paper-based electrochemical biosensor C-reactive protein detection",
        "C-reactive protein immunosensor ELISA sensitivity whole blood",
        "CRP biosensor 0.5 mg/L whole blood electrochemical",
    ],
    DomainRoute.animal_gut_health: [
        "Lactobacillus rhamnosus GG C57BL/6 intestinal permeability FITC-dextran",
        "LGG tight junction claudin-1 occludin mouse gut permeability",
        "probiotic Lactobacillus rhamnosus GG FITC-dextran assay mice",
    ],
    DomainRoute.microbial_electrochemistry: [
        "Sporomusa ovata bioelectrochemical CO2 acetate cathode potential",
        "Sporomusa ovata microbial electrosynthesis acetate CO2",
        "-400 mV SHE Sporomusa ovata acetate production",
    ],
}


KNOWN_HELA_URLS = {
    "atcc_ccl2": "https://www.atcc.org/products/ccl-2",
    "thermo_gibco_freezing": "https://www.thermofisher.com/us/en/home/references/gibco-cell-culture-basics/cell-culture-protocols/freezing-cells.html",
    "promega_celltiter_glo": "https://worldwide.promega.com/resources/protocols/technical-bulletins/0/celltiter-glo-luminescent-cell-viability-assay-protocol/",
}


@dataclass(frozen=True)
class EvidenceRecipe:
    protocol_queries: list[str]
    openwetware_queries: list[str]
    supplier_queries: list[str]
    standards: list[str]
    include_literature_methods: bool = True
    allow_bio_protocol_discovery: bool = False
    allow_supplier_extract_urls: list[str] | None = None


class SourceRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.semantic_scholar = SemanticScholarProvider(settings)
        self.europe_pmc = EuropePmcProvider(settings)
        self.ncbi = NcbiEutilsProvider(settings)
        self.arxiv = ArxivProvider(settings)
        self.protocols = ProtocolsIoProvider(settings)
        self.openwetware = OpenWetWareProvider(settings)

    def literature_primary_providers(self) -> list:
        return [self.semantic_scholar, self.europe_pmc]

    def ncbi_provider(self) -> NcbiEutilsProvider:
        return self.ncbi

    def arxiv_provider(self) -> ArxivProvider:
        return self.arxiv

    def evidence_recipe(self, domain_route: DomainRoute) -> EvidenceRecipe:
        if domain_route == DomainRoute.cell_biology:
            return EvidenceRecipe(
                protocol_queries=PROTOCOL_QUERY_PACKS[domain_route],
                openwetware_queries=[
                    "Marek Freeze-down Thaw",
                    "TissueCulture Thawing cells",
                    "Shreffler Cryopreservation",
                ],
                supplier_queries=[
                    "Sigma trehalose product page",
                    "Thermo Trypan Blue mammalian cell viability",
                    "Gibco cell freezing supplies",
                ],
                standards=["bmbl"],
                include_literature_methods=True,
                allow_supplier_extract_urls=[
                    KNOWN_HELA_URLS["atcc_ccl2"],
                    KNOWN_HELA_URLS["thermo_gibco_freezing"],
                    KNOWN_HELA_URLS["promega_celltiter_glo"],
                ],
            )
        if domain_route == DomainRoute.diagnostics_biosensor:
            return EvidenceRecipe(
                protocol_queries=PROTOCOL_QUERY_PACKS[domain_route],
                openwetware_queries=["Real-time PCR", "immunoassay"],
                supplier_queries=[
                    "anti-CRP antibody Sigma product page",
                    "Human CRP ELISA Thermo product page",
                    "CRP assay material supplier page",
                ],
                standards=["stard"],
                include_literature_methods=True,
                allow_bio_protocol_discovery=True,
            )
        if domain_route == DomainRoute.animal_gut_health:
            return EvidenceRecipe(
                protocol_queries=PROTOCOL_QUERY_PACKS[domain_route],
                openwetware_queries=["Lactobacillus culture"],
                supplier_queries=["Lactobacillus rhamnosus GG supplier"],
                standards=["arrive", "miqe"],
                include_literature_methods=True,
            )
        return EvidenceRecipe(
            protocol_queries=PROTOCOL_QUERY_PACKS[DomainRoute.microbial_electrochemistry],
            openwetware_queries=[],
            supplier_queries=[],
            standards=["anaerobic_safety"],
            include_literature_methods=True,
        )

    def literature_query_examples(self, domain_route: DomainRoute) -> list[str]:
        return list(LITERATURE_QUERY_EXAMPLES[domain_route])
