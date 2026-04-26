from app.models.schemas import Preset


PRESETS: list[Preset] = [
    Preset(
        id="crp-biosensor",
        label="Diagnostics / CRP biosensor",
        domain="diagnostics",
        optimized_demo=False,
        hypothesis=(
            "A paper-based electrochemical biosensor functionalized with anti-CRP antibodies will detect "
            "C-reactive protein in whole blood at concentrations below 0.5 mg/L within 10 minutes, matching "
            "laboratory ELISA sensitivity without requiring sample preprocessing."
        ),
    ),
    Preset(
        id="lgg-mouse-gut",
        label="Gut health / Lactobacillus mouse study",
        domain="gut health",
        optimized_demo=False,
        hypothesis=(
            "Supplementing C57BL/6 mice with Lactobacillus rhamnosus GG for 4 weeks will reduce intestinal "
            "permeability by at least 30% compared to controls, measured by FITC-dextran assay, due to "
            "upregulation of tight junction proteins claudin-1 and occludin."
        ),
    ),
    Preset(
        id="sporomusa-co2",
        label="Climate / Sporomusa ovata CO2 fixation",
        domain="climate biotech",
        optimized_demo=False,
        hypothesis=(
            "Introducing Sporomusa ovata into a bioelectrochemical system at a cathode potential of -400 mV "
            "vs SHE will fix CO2 into acetate at a rate of at least 150 mmol/L/day, outperforming current "
            "biocatalytic carbon capture benchmarks by at least 20%."
        ),
    ),
    Preset(
        id="hela-trehalose",
        label="Main demo / HeLa cryopreservation",
        domain="cell biology",
        optimized_demo=True,
        hypothesis=(
            "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase "
            "post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard "
            "DMSO protocol, due to trehalose's superior membrane stabilization at low temperatures."
        ),
    ),
]


def get_preset(preset_id: str | None) -> Preset | None:
    if preset_id is None:
        return None
    return next((preset for preset in PRESETS if preset.id == preset_id), None)

