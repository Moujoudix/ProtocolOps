from app.models.schemas import DomainRoute


PRESET_DOMAIN_ROUTE_MAP: dict[str, DomainRoute] = {
    "hela-trehalose": DomainRoute.cell_biology,
    "crp-biosensor": DomainRoute.diagnostics_biosensor,
    "lgg-mouse-gut": DomainRoute.animal_gut_health,
    "sporomusa-co2": DomainRoute.microbial_electrochemistry,
}


DOMAIN_LABELS: dict[DomainRoute, str] = {
    DomainRoute.cell_biology: "cell biology",
    DomainRoute.diagnostics_biosensor: "diagnostics / biosensor",
    DomainRoute.animal_gut_health: "animal gut health",
    DomainRoute.microbial_electrochemistry: "microbial electrochemistry",
}


def resolve_domain_route(hypothesis: str, preset_id: str | None = None) -> DomainRoute:
    if preset_id and preset_id in PRESET_DOMAIN_ROUTE_MAP:
        return PRESET_DOMAIN_ROUTE_MAP[preset_id]

    lowered = hypothesis.lower()
    if "hela" in lowered or "cryoprotect" in lowered or "post-thaw" in lowered:
        return DomainRoute.cell_biology
    if "biosensor" in lowered or "crp" in lowered or "electrochemical" in lowered:
        return DomainRoute.diagnostics_biosensor
    if "c57bl/6" in lowered or "lactobacillus" in lowered or "fitc-dextran" in lowered:
        return DomainRoute.animal_gut_health
    return DomainRoute.microbial_electrochemistry


def domain_label_for_route(domain_route: DomainRoute) -> str:
    return DOMAIN_LABELS[domain_route]

