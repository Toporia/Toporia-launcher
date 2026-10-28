"""Mathematical help for the original built-in presets, without changing recipes.

Deliberately restricted to known original modules. Unknown/plugin presets retain
the optional-description API and can declare their own DESCRIPTION.
"""

import re

from toporia.framework.problem.solver import Solver

from ._research import Equation, ResearchDescription

ORIGINALS = {
    "cantilever", "cantilever_3d", "column_buckling", "drone_arm", "drone_arm_camera_view",
    "drone_arm_point_loads", "force_inverter", "heat_sink", "l_bracket", "l_bracket_stress",
    "mbb_beam", "mbb_beam_fixed_projection", "mbb_beam_robust", "michell_cantilever",
    "nonlinear_cantilever", "standard_bar", "three_point_bending", "vibrating_beam",
}
RELATED = {
    "h8": "solid3d", "q4_heat": "heat2d", "q4_dynamic": "dynamic",
    "q4_buckling": "buckling", "q4_nonlinear": "nonlinear", "q4_mechanism": "mechanism",
}
PHYSICS = {"q4": "q4_plane_stress", "h8": "h8_solid"}


def original_description(module):
    if module.__name__.rsplit(".", 1)[-1] not in ORIGINALS:
        return None
    from toporia.plugins.methods import method_class

    from ._research_batch4 import CASES, ELASTIC

    scenario = module.scenario()
    solver = module.solver() if hasattr(module, "solver") else Solver()
    model, updater = method_class(solver.method).name.split("+")
    related = RELATED.get(model)
    equations = CASES[related]["equations"] if related else (Equation(*ELASTIC),)
    if related == "buckling" and scenario.objective["type"] != "buckling_load":
        equations = (Equation(*ELASTIC),) + tuple(
            Equation(e.latex.replace("J=", "g_B="), "Buckling constraint: " + e.explanation)
            for e in equations)
    if any(spec["type"] == "local_stress" for spec in scenario.constraints):
        equations += CASES["local_stress"]["equations"]
    if scenario.objective["type"] == "volume":
        equations += (Equation(r"J=\sum_e\rho_e", "This preset minimizes summed physical density under its declared stress constraint; the built-in material budget is a separate upper bound."),)
    equations += (Equation(
        r"\rho=P(R(z)),\quad\nabla_zJ=J_R^{\mathsf{T}}J_P^{\mathsf{T}}\nabla_\rho J",
        "The representation and configured filters map variables to the physical field; their adjoints carry sensitivities back."),)
    if solver.variants:
        equations += (Equation(r"J_{\rm worst}=\frac{s}{a}\log\sum_i e^{aJ_i/s}",
                              "The configured shared-variable variants use a smooth worst case. The scale s is held fixed inside an iteration; volume/display use the declared nominal variant."),)
    functions = ["model:"+model, "physics:"+PHYSICS.get(model, model), "updater:"+updater,
                 "representation:"+solver.representation.get("type", "element_density"),
                 "interpolation:"+solver.interpolation.get("type", "simp"), "response:"+scenario.objective["type"]]
    functions += ["response:"+c["type"] for c in scenario.constraints]
    functions += ["filter:"+spec["type"] for spec in solver.filter_specs]
    functions += ["schedule:"+spec["type"] for spec in solver.schedules]
    reference = getattr(module, "REFERENCE", "")
    urls = re.findall(r"https?://[^\s]+", reference)
    supports = (f"Edges {scenario.edge_constraints}; points {scenario.point_constraints}; "
                f"loads {scenario.point_loads}; load cases {scenario.load_cases}; holes {scenario.holes}; "
                f"springs {scenario.point_springs}; enforced areas {scenario.enforced_areas}.")
    return ResearchDescription(
        question=getattr(module, "ABOUT", module.NAME),
        setup=f"Original general-purpose preset: {module.NAME}. Domain {scenario.Lx} by {scenario.Ly} by {scenario.Lz}; "
              f"mesh resolution {solver.m}; volume budget {scenario.volfrac}; E0={scenario.E0}, Emin={scenario.Emin}, nu={scenario.nu}. "
              f"{supports} Method {solver.method}; cap {solver.max_iter}; tolerance {solver.tol}; "
              f"parameters {solver.method_params}; representation {solver.representation}; material {solver.interpolation}; "
              f"filters {solver.filter_specs}; objective {scenario.objective}; constraints {scenario.constraints}; "
              f"schedules {solver.schedules}; variants {solver.variants}.",
        computes=(CASES[related]["computes"] if related else
                  "The current linear elastic model maps the design through its filters/material, solves equilibrium, evaluates the selected responses and their adjoints, and updates variables with the configured updater.") +
                 " The associated research demonstration uses separately declared settings; selecting this preset does not silently substitute that experiment.",
        equations=equations,
        symbols=(CASES[related]["symbols"] if related else "K: stiffness; u/F: displacement/load; E: modulus; C: compliance.") +
                " rho: physical density; z: design variables; R/P: representation/filter maps; J: selected scalar objective; "
                "J_R/J_P: Jacobians; superscript T: transpose. In the variant expression a is sharpness, s the frozen scale and i a variant. "
                "The displayed equations describe the core model; the exact objective/constraints/filter settings are stated above and explained by their own help topics.",
        source_url=urls[0] if urls else "", figure="General-purpose preset, not a newly certified paper-figure reproduction. Related function examples: " +
        ("Batch 4 case " + related if related else "Batch 1 linear-elastic baseline and the function census"),
        comparison="Use the research census and per-case reports for native/analytic/figure evidence. This original preset retains its own geometry, loads, parameters and stopping rule.",
        limitations=(CASES[related]["limits"] if related else
                     "Numerical regularization, mesh resolution, grayness, nonconvex optimization and finite stopping tolerances limit interpretation. A finished run need not meet every constraint or reproduce a paper.") +
                    " These model equations do not replace the selected updater, response and filter definitions. Inspect fresh physical metrics and constraint reports.",
        reproduce='toporia run "'+module.NAME+'"', functions=tuple(dict.fromkeys(functions)))
