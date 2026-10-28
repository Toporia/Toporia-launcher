"""Mathematical help for the original built-in presets, without changing recipes.

Deliberately restricted to known original modules. Unknown/plugin presets retain
the optional-description API and can declare their own DESCRIPTION.

Everything shown is read from the preset's actual scenario and solver, so the
help cannot drift from what the preset runs. The setup is written as plain
sentences; the equations come from the shared research cases of the parts in use.
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
THERMAL = {"q4_heat", "h8_heat", "pymoto_heat"}
#: The plain parts nearly every preset uses; they are not singled out as "try it on its own".
BASELINE = {"model:q4", "updater:oc", "representation:element_density",
            "interpolation:simp", "response:compliance", "filter:density"}
DOFS = {"both": "x and y"}
DIRECTIONS = {0: "+x (right)", 90: "+y (up)", 180: "-x (left)", 270: "-y (down)"}


def _n(value):
    """A number as a person writes it: 60 rather than 60.0, 0.0152 rather than 0.015151515151515152."""
    return f"{value:.3g}" if isinstance(value, float) else str(value)


def _settings(spec, skip=("type",)):
    """{'type': 'density', 'rmin': 1.5} -> 'rmin 1.5'; empty when only defaults are used."""
    return ", ".join(f"{key} {_n(value)}" for key, value in spec.items() if key not in skip)


def _label(kind, name):
    """The display label of a registered part, or its config name when it has none."""
    from toporia.plugins.filters import FILTERS
    from toporia.plugins.interpolations import INTERPOLATIONS
    from toporia.plugins.representations import REPRESENTATIONS
    from toporia.plugins.responses import RESPONSES
    from toporia.plugins.schedules import SCHEDULES
    registry = {"filter": FILTERS, "interpolation": INTERPOLATIONS, "representation": REPRESENTATIONS,
                "response": RESPONSES, "schedule": SCHEDULES}[kind]
    try:
        return registry.get(name).label or name
    except Exception:
        return name


def _part(kind, spec, default):
    extra = _settings(spec)
    return _label(kind, spec.get("type", default)) + (f" ({extra})" if extra else " (default settings)")


def _direction(angle):
    return DIRECTIONS.get(int(angle) % 360, f"{_n(angle)} degrees from +x")


def _setup(scenario, solver, model):
    """The preset's setup as short plain sentences, one topic per line."""
    s = scenario
    thermal = model in THERMAL
    nx, ny = round(s.Lx * solver.m), round(s.Ly * solver.m)
    per_mm = f"{solver.m:g} element{'' if solver.m == 1 else 's'} per mm"
    if s.Lz:
        domain = (f"{_n(s.Lx)} x {_n(s.Ly)} x {_n(s.Lz)} mm box, {per_mm} "
                  f"({nx} x {ny} x {round(s.Lz * solver.m)} elements).")
    else:
        domain = f"{_n(s.Lx)} x {_n(s.Ly)} mm plate, {per_mm} ({nx} x {ny} elements)."
    lines = [f"Domain: {domain}"]

    supports = [f"{e.edge} edge fixed in {DOFS.get(e.dof, e.dof)}" for e in s.edge_constraints]
    supports += [f"point ({_n(p.x)}, {_n(p.y)}) fixed in {DOFS.get(p.dof, p.dof)}" for p in s.point_constraints]
    supports += [f"{'sink' if thermal else 'clamped'} ring at ({_n(h.cx)}, {_n(h.cy)}), radius {_n(h.r_passive)}"
                 for h in s.holes if h.kind == "fixed"]
    if supports:
        lines.append(("Heat sinks (temperature fixed): " if thermal else "Supports: ") + "; ".join(supports) + ".")

    if thermal:
        lines.append("Heat input: uniform over the whole domain.")
    else:
        where = [f"({_n(p.x)}, {_n(p.y)})" for p in s.point_loads]
        where += [f"the ring of hole ({_n(h.cx)}, {_n(h.cy)})" for h in s.holes if h.kind == "load"]
        several = len(s.load_cases) > 1
        cases = [f"{_n(c.Fmag)} towards {_direction(c.Fa)}" + (f", weight {_n(c.weight)}" if several else "")
                 for c in s.load_cases]
        mass = solver.method_params.get("attached_mass", 0)
        if where and s.objective.get("type") == "eigenfrequency":
            lines.append(f"Payload: mass {_n(mass)} spread over {', '.join(where)}; "
                         "a frequency objective uses no force, so the load point only marks where the payload sits.")
        elif where:
            lines.append(f"Loads at {', '.join(where)}; "
                         + (f"{len(cases)} load cases: " if several else "force ") + "; ".join(cases) + ".")
            if mass:
                lines.append(f"Payload: mass {_n(mass)} spread over the load points.")
    if s.point_springs:
        lines.append("Springs: " + "; ".join(f"stiffness {_n(p.stiffness)} in {p.dof} at ({_n(p.x)}, {_n(p.y)})"
                                             for p in s.point_springs) + ".")
    for area in s.enforced_areas:
        corners = ", ".join(f"({_n(x)}, {_n(y)})" for x, y in area.points)
        lines.append(f"Area forced {'empty' if area.kind == 'empty' else 'solid'}: polygon {corners}.")

    if thermal:
        lines.append(f"Material: conductivity {_n(s.E0)} for solid, {_n(s.Emin)} for void.")
    else:
        lines.append(f"Material: Young's modulus {_n(s.E0)} for solid, {_n(s.Emin)} for void, "
                     f"Poisson ratio {_n(s.nu)}.")
    lines.append(f"Volume budget: at most {s.volfrac:.0%} of the domain may be material.")

    goal = _part("response", s.objective, "compliance")
    lines.append(f"Objective: {goal}." if "maximise" in goal else f"Objective: minimise {goal}.")
    if s.constraints:
        lines.append("Constraints: " + "; ".join(_part("response", c, "") for c in s.constraints) + ".")

    stop = (f"stops when the design changes by less than {solver.tol:g}, at most {solver.max_iter} iterations"
            if solver.tol > 0 else f"runs all {solver.max_iter} iterations")
    params = _settings(solver.method_params, skip=())
    lines.append(f"Method: {solver.method}" + (f" with {params}" if params else "") + f"; {stop}.")
    lines.append(f"Design variables: {_part('representation', solver.representation, 'element_density')}; "
                 f"material law: {_part('interpolation', solver.interpolation, 'simp')}.")
    if solver.filter_specs:
        lines.append("Filters, in order: "
                     + "; then ".join(_part("filter", f, "density") for f in solver.filter_specs) + ".")
    for schedule in solver.schedules:
        lines.append(f"Continuation: {_label('schedule', schedule.get('type', ''))} on {schedule.get('path', '?')} "
                     f"({_settings(schedule, skip=('type', 'path'))}).")
    if solver.variants:
        v = solver.variants
        lines.append(f"Robust variants: {v.get('path')} takes the values "
                     f"{', '.join(_n(x) for x in v.get('values', ()))}; the {v.get('combine', 'worst')} case is optimised.")
    return "\n".join(lines)


def _try_alone(functions):
    """For each non-baseline part of this preset, the research presets that demonstrate it."""
    from toporia.plugins.problems import _modules
    users = {}
    for name, module in _modules().items():
        for function in getattr(getattr(module, "DESCRIPTION", None), "functions", ()):
            users.setdefault(function, []).append(name)
    lines = []
    for function in functions:
        if function in BASELINE or function.startswith("physics:"):
            continue
        demos = sorted(name for name in users.get(function, ()) if name.startswith(("Research:", "Paper:")))
        if demos:
            lines.append(f"{function}: {', '.join(demos[:3])}")
    return lines


def _elastic(solver, objective):
    spec = solver.interpolation
    law = ""
    if spec.get("type", "simp") == "simp":
        law = rf",\quad E(\rho)=E_{{\min}}+(E_0-E_{{\min}})\rho^{{{spec.get('penal', 3.0):g}}}"
    if objective == "compliance":
        return Equation(r"K(\rho)u=F,\quad C=F^{\mathsf{T}}u" + law,
                        "Each element's density sets its stiffness; the equilibrium solve gives the displacement u, "
                        "and minimising the compliance C (the work done by the load) makes the structure stiff.")
    return Equation(r"K(\rho)u=F" + law,
                    "Each element's density sets its stiffness; the equilibrium solve gives the displacement u "
                    "that the objective and constraints below are computed from.")


def original_description(module):
    if module.__name__.rsplit(".", 1)[-1] not in ORIGINALS:
        return None
    from toporia.plugins.methods import method_class

    from ._research_batch2 import CASES as FILTER_CASES
    from ._research_batch4 import CASES

    scenario = module.scenario()
    solver = module.solver() if hasattr(module, "solver") else Solver()
    model, updater = method_class(solver.method).name.split("+")
    related = RELATED.get(model)
    objective = scenario.objective.get("type", "compliance")
    projected = any(spec.get("type") == "heaviside" for spec in solver.filter_specs)

    equations = CASES[related]["equations"] if related else (_elastic(solver, objective),)
    if related == "buckling" and objective != "buckling_load":
        equations = (Equation(r"K(\rho)u=F,\quad C=F^{\mathsf{T}}u",
                              "The objective is ordinary compliance from the linear equilibrium solve."),) + tuple(
            Equation(e.latex.replace("J=", "g_B="), "Buckling constraint (g_B <= 0): " + e.explanation)
            for e in equations)
    if any(spec["type"] == "local_stress" for spec in scenario.constraints):
        equations += CASES["local_stress"]["equations"]
    if objective == "volume":
        equations += (Equation(r"J=\sum_e\rho_e",
                               "This preset minimises the material used, subject to its stress constraint; "
                               "the volume budget above is only an upper bound."),)
    if projected:
        equations += FILTER_CASES["heaviside"]["equations"][:1]
    equations += (Equation(
        r"\rho=P(R(z)),\quad\nabla_zJ=J_R^{\mathsf{T}}J_P^{\mathsf{T}}\nabla_\rho J",
        "The design variables z become the physical densities through the representation R and the filters P; "
        "the chain rule carries the sensitivities back through both."),)
    if solver.variants:
        equations += (Equation(r"J_{\rm worst}=\frac{s}{a}\log\sum_i e^{aJ_i/s}",
                               "The variants share one set of variables and a smooth maximum picks the worst. The scale s "
                               "is held fixed inside an iteration; volume and display use the declared nominal variant."),)

    functions = ["model:"+model, "physics:"+PHYSICS.get(model, model), "updater:"+updater,
                 "representation:"+solver.representation.get("type", "element_density"),
                 "interpolation:"+solver.interpolation.get("type", "simp"), "response:"+objective]
    functions += ["response:"+c["type"] for c in scenario.constraints]
    functions += ["filter:"+spec["type"] for spec in solver.filter_specs]
    functions += ["schedule:"+spec["type"] for spec in solver.schedules]
    functions = tuple(dict.fromkeys(functions))

    symbols = (CASES[related]["symbols"] + " ") if related else \
        "K: stiffness matrix; u/F: displacement/load; E: Young's modulus; C: compliance. "
    symbols += ("rho: physical density; z: design variables; R/P: representation/filter maps; J: the objective; "
                "J_R/J_P: their Jacobians; superscript T: transpose.")
    if projected:
        symbols += " In the projection: x is the filtered density, beta the sharpness, eta the threshold."
    if solver.variants:
        symbols += " In the worst case: a is the sharpness, s the frozen scale and i a variant."
    demos = _try_alone(functions)
    urls = re.findall(r"https?://[^\s]+", getattr(module, "REFERENCE", ""))
    return ResearchDescription(
        question=getattr(module, "ABOUT", module.NAME),
        setup=_setup(scenario, solver, model),
        computes=(CASES[related]["computes"] if related else
                  "Each iteration maps the design through its filters and material law, solves the elastic equilibrium, "
                  "evaluates the objective and constraints with their sensitivities, and updates the design with the "
                  "chosen updater."),
        equations=equations,
        symbols=symbols,
        source_url=urls[0] if urls else "",
        figure="General-purpose preset: it shows a typical use, not a reproduced paper figure."
               + (" To try its parts on their own, open these presets: " + "; ".join(demos) + "." if demos else ""),
        comparison="The research census and per-case reports hold the analytic, native-code and paper comparisons. "
                   "This preset keeps its own geometry, loads, parameters and stopping rule.",
        limitations=(CASES[related]["limits"] if related else
                     "Mesh resolution, grey material, a non-convex search and a finite stopping tolerance all limit what "
                     "one run shows. A finished run need not meet every constraint.")
                    + " Check the final metrics and constraint report of the run itself.",
        reproduce='toporia run "'+module.NAME+'"', functions=functions)
