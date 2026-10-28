"""Existing physics, response and saved-field post-processing demonstrations.

python -m experiments.research_batch4 [--case NAME] [--strict-paper]
No paper figure match is inferred from analytic or cross-implementation checks.
Post-processing reuses fields; it does not rerun their optimizations.
"""

import argparse
import contextlib
import hashlib
import json
import struct
import time
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import numpy as np

from experiments.research_batch3 import dump, versions
from toporia.apps.research_render import description_page
from toporia.engine.loop import _loop, initialized_method
from toporia.engine.records import ResultStore
from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Scenario
from toporia.framework.params import resolve_params
from toporia.framework.parts.postprocess import Result
from toporia.framework.problem.files import to_dict
from toporia.framework.problem.mesh import make_problem
from toporia.framework.problem.run import Run
from toporia.plugins.postprocessors import POSTPROCESSORS
from toporia.plugins.problems._research_batch4 import CASES, POSTS, description, metadata, recipe

ROOT = Path(__file__).resolve().parents[1]


def figure_grid():
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    figure = Figure(figsize=(11, 7), dpi=150, facecolor="white")
    FigureCanvasAgg(figure)
    return figure, figure.subplots(2, 2)


def field_plot(ax, field, title):
    field = np.asarray(field)
    if field.ndim == 3:
        field = field.mean(axis=0)
        title += " (mean through depth)"
    ax.imshow(field, origin="lower", cmap="gray_r", vmin=0, vmax=1, interpolation="nearest")
    ax.set(title=title, xlabel="x cell index", ylabel="y cell index")


#: Central-difference steps other than the default 1e-6. The multiresolution showcase sums a compliance
#: near 1000 over 4800 cells; below 1e-5 the coarse saddle-point solve's round-off dominates
#: (relative error 1.4e-3 at 1e-6, 7e-6 at 1e-4, 3e-8 at 1e-2), as its unit test also notes.
PROBE_STEPS = {"multires": 1e-4}


def gradient_probe(name):
    """Differentiate a separate smooth design with parameters held fixed."""
    scenario, solver = recipe(name)
    if name == "stress_volume":
        scenario = replace(scenario, constraints=[dict(type="stress", limit=3., adaptive=False)])
    with contextlib.redirect_stdout(None):
        method = initialized_method(Run(scenario, solver))
    model = method._model
    rng = np.random.default_rng(4222)
    lower, upper = model.bounds()
    z = np.clip(model.initial_design()+rng.uniform(-.025, .025, lower.shape), lower, upper)
    direction = rng.normal(size=z.shape)
    direction[upper == lower] = 0.
    direction /= np.linalg.norm(direction)
    h = PROBE_STEPS.get(name, 1e-6)
    try:
        base = model.evaluate(z)
        high, low = model.evaluate(z+h*direction, gradients=False), model.evaluate(z-h*direction, gradients=False)
        triples = [(base.objective_gradient, high.objective, low.objective),
                   (base.volume_gradient, high.volume, low.volume)]
        triples += [(a.gradient, b.value, c.value) for a, b, c in zip(base.constraints, high.constraints, low.constraints, strict=True)]
        errors = []
        for gradient, a, b in triples:
            fd = (a-b)/(2*h)
            adjoint = float(np.sum(gradient*direction))
            errors.append(float(abs(fd-adjoint)/max(1., abs(fd), abs(adjoint))))
        checks = dict(directional_gradient_errors=errors, gradient_tolerance=3e-3, probe_step=h,
                      checks_passed=max(errors) < 3e-3,
                      scope="Objective, budget and every extra constraint at one smooth deterministic direction. Stress adaptive scale disabled only in the probe; eigenvalue reference and AL multipliers held fixed. Not certification at switches/repeated modes.")
    finally:
        method.close()
    return checks


def analytic_heat(dim):
    from toporia.plugins.physics.h8_heat import H8Heat
    from toporia.plugins.physics.q4_heat import Q4Heat
    cls = H8Heat if dim == 3 else Q4Heat
    scenario = Scenario(Lx=8., Ly=2., Lz=2. if dim == 3 else 0.,
                        edge_constraints=[EdgeConstraint("left"), EdgeConstraint("right")], load_cases=[LoadCase(Fmag=0.)])
    rows = []
    for m in (1., 2., 4.):
        problem = make_problem(scenario, m)
        engine = cls()
        engine.initialize(problem, dict(heat_source=.5))
        state = engine.solve(np.ones(problem.shape))
        exact_c = .5**2*2*(2 if dim == 3 else 1)*(8**3-problem.dx**2*8)/12
        actual_c = float(engine.thermal_compliance(state, 0))
        rows.append([m, float(state.T.max()), 4., actual_c, exact_c])
    error = max(abs(r[1]-r[2])/4 for r in rows)
    cerror = max(abs(r[3]-r[4])/r[4] for r in rows)
    return dict(heat_strip_max_temperature_relative_error=error, heat_strip_discrete_compliance_relative_error=cerror,
                heat_strip_parameters=dict(Lx=8., Ly=2., Lz=2. if dim == 3 else 0., heat_source=.5, conductivity=1., end_temperatures=0., resolutions=[1., 2., 4.]),
                heat_strip_pass=error < 1e-9 and cerror < 1e-9), rows


def library_probe(name):
    """Disable both spatial filters for a common random-field assembly check."""
    native = dict(elastic_pymoto="q4", heat_pymoto="q4_heat", dynamic_pymoto="q4_dynamic")[name]
    scenario, solver = recipe(name)
    foreign_solver = replace(solver, method_params={**solver.method_params, "rmin": 1.})
    native_solver = replace(solver, method=native+"+mma", filter_specs=[],
                            method_params=dict(attached_mass=2.) if name == "dynamic_pymoto" else {})
    methods = []
    try:
        with contextlib.redirect_stdout(None):
            methods = [initialized_method(Run(scenario, s)) for s in (foreign_solver, native_solver)]
        model_f, model_n = [m._model for m in methods]
        # pyMOTO's network establishes its normalization during initialization;
        # establish the native reference at the same uniform starting field.
        model_f.evaluate(model_f.initial_design(), gradients=False)
        model_n.evaluate(model_n.initial_design(), gradients=False)
        lower, upper = model_n.bounds()
        z = np.clip(np.random.default_rng(427).uniform(.3, .8, lower.shape), lower, upper)
        foreign, native_result = model_f.evaluate(z.ravel()), model_n.evaluate(z)
        if name == "dynamic_pymoto":
            a, b = foreign.reported["omega_1"], native_result.reported["omega_1"]
        else:
            a, b = foreign.objective, native_result.objective
        error = float(abs(a-b)/max(abs(a), abs(b), 1e-30))
        free = upper > lower
        ga = foreign.objective_gradient.reshape(z.shape)[free]
        gb = native_result.objective_gradient[free]
        gerror = float(np.max(abs(ga-gb))/max(1., np.max(abs(ga)), np.max(abs(gb))))
        return dict(independent_library_value_relative_error=error, independent_library_gradient_error=gerror,
                    library_probe_pass=error < 1e-5 and gerror < 1e-5,
                    library_probe_scope="Same random design and uniform-start objective references; both filters disabled; free-variable gradients only; native/foreign assembly, not a source-paper figure.")
    finally:
        for method in methods:
            method.close()


def special_probe(name, folder):
    extra, rows = {}, None
    if name in {"heat2d", "heat3d"}:
        extra, rows = analytic_heat(3 if name == "heat3d" else 2)
    if name.endswith("_pymoto"):
        extra = library_probe(name)
    if name == "solid3d":
        from experiments.original_references import validate
        ref = json.loads((ROOT / "tests/references/matlab.json").read_text(encoding="utf-8"))
        native = next(c for c in ref["cases"] if c["name"] == "top3d_density")
        with contextlib.redirect_stdout(None):
            actual = validate(native)
        keys = ("first_reported_compliance", "last_reported_compliance")
        errors = {k: abs(actual[k]-native[k]) for k in keys}
        extra = dict(native_scalar_errors=errors, native_scalar_same_iterations=actual["iterations"] == native["iterations"],
                     native_scalar_pass=max(errors.values()) < 5.1e-5 and actual["iterations"] == native["iterations"],
                     native_scalar_scope="Fresh Python probe vs previously captured author first/last printed values and 39 stops. Explicit uniform depth-node shares in this probe only; no native final field comparison.")
        fixture = ROOT / "tests/references/matlab.json"
        dump(folder / "native-scalar-comparison.json", dict(actual=actual, reference=native, checks=extra,
             author_source=ref["sources"].get("top3d.m"), fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
             native_capture_date=ref["captured_on"], native_runtime=ref["runtime"]))
    if name == "phase_field":
        from scipy.special import expit

        from toporia.plugins.responses.phase_field import phase_energy, physical_laplacian
        rows = []
        for h in (.4, .2, .1, .05):
            x = (np.arange(round(40/h))+.5)*h-20
            rho = expit(np.sqrt(2)*x)[None, :]
            value, _ = phase_energy(rho, physical_laplacian(rho.shape, (h, h)), 1.)
            integral = value*40.
            rows.append([h, integral, np.sqrt(2)/6])
        error = float(abs(rows[-1][1]-rows[-1][2])/rows[-1][2])
        extra = dict(planar_interface_relative_error=error, planar_interface_pass=error < 1e-3)
    if name == "dynamic":
        from toporia.plugins.physics.q4_dynamic import Q4Dynamic
        scenario = Scenario(Lx=20., Ly=1., nu=0., edge_constraints=[EdgeConstraint("left", "both")],
                            point_loads=[PointLoad(20., .5)], load_cases=[LoadCase(Fmag=1., Fa=270.)])
        rows = []
        reference = 1.8751040687**2*np.sqrt(1/12/20**4)
        for m in (2., 4., 6.):
            problem = make_problem(scenario, m)
            engine = Q4Dynamic()
            engine.initialize(problem, resolve_params("q4_dynamic", engine.params, dict(low_density_below=0.)))
            state = engine.solve(np.ones(problem.shape))
            w = float(np.sqrt(engine.eigenvalues(state, 1)[0]))
            rows.append([m, w, reference])
        error = float(abs(rows[-1][1]-reference)/reference)
        extra = dict(euler_bernoulli_relative_error=error, beam_frequency_pass=error < .03)
    if name == "buckling":
        from toporia.plugins.physics.q4_buckling import Q4Buckling
        scenario = Scenario(Lx=40., Ly=4., edge_constraints=[EdgeConstraint("left", "both")],
                            point_loads=[PointLoad(40., j/2) for j in range(9)],
                            load_cases=[LoadCase(Fmag=1/9, Fa=180.)])
        problem = make_problem(scenario, 2.)
        engine = Q4Buckling()
        engine.initialize(problem, resolve_params("q4_buckling", engine.params, {}))
        value = float(engine.buckling_factors(engine.solve(np.ones(problem.shape)), 0, 1)[0])
        reference = np.pi**2*(4**3/12)/(4*40**2)
        error = abs(value-reference)/reference
        extra = dict(euler_column_load=value, euler_reference=reference, euler_column_relative_error=error, euler_column_pass=error < .04)
    if name == "nonlinear":
        scenario, solver = recipe(name)
        scenario = replace(scenario, load_cases=[LoadCase(Fmag=1e-5, Fa=270.)])
        values = []
        for method_name, objective in (("q4_nonlinear+mma", "end_compliance"), ("q4+mma", "compliance")):
            with contextlib.redirect_stdout(None):
                method = initialized_method(Run(replace(scenario, objective=dict(type=objective)),
                                                replace(solver, method=method_name, method_params={})))
            try:
                values.append(float(method._model.evaluate(method.x, gradients=False).objective))
            finally:
                method.close()
        error = abs(values[0]-values[1])/values[1]
        extra = dict(small_load_relative_difference=error, small_load_linear_limit_pass=error < 1e-3)
    if name == "mechanism":
        scenario, solver = recipe(name)
        with contextlib.redirect_stdout(None):
            method = initialized_method(Run(scenario, solver))
        try:
            model = method._model
            rho = model.physical(method.x)
            state = model.engine.solve(rho)
            probe = model.engine.point_probe(40., 20., 180.)
            force = model.engine.layout.forces[0][1]
            reversed_u = model.engine.adjoint(state, probe)
            forward = float(np.dot(probe, state.U[:, 0]))
            reversed_value = float(np.dot(force, reversed_u))
            error = abs(forward-reversed_value)/max(abs(forward), 1e-20)
            extra = dict(maxwell_betti_relative_error=error, reciprocity_pass=error < 1e-9)
        finally:
            method.close()
    if name == "minimum_length":
        from toporia.plugins.responses.minimum_length import MinimumLength
        problem = make_problem(Scenario(Lx=50., Ly=40.), 1.)
        part = MinimumLength()
        part.setup(None, problem, resolve_params(part.name, part.params, dict(min_length=10.)))
        rows = []
        for width in (4, 8, 12):
            rho = np.zeros(problem.shape)
            rho[20-width//2:20+width//2, :] = 1.
            value = float(part.measure(rho, gradient=False)[0])
            rows.append([width, value, 1.])
        extra = dict(straight_bar_indicators=rows, length_indicator_pass=rows[0][1] > 1 and rows[-1][1] <= 1)
    if rows is not None:
        np.savetxt(folder / "analytic-curve.csv", rows, delimiter=",")
    return extra


def science_case(name, output, max_iter=None):
    folder = Path(output) / name
    folder.mkdir(parents=True, exist_ok=True)
    checks = gradient_probe(name)
    checks.update(special_probe(name, folder))
    checks["checks_passed"] &= all(v for k, v in checks.items() if k.endswith("_pass"))
    scenario, solver = recipe(name)
    if max_iter is not None:
        solver = replace(solver, max_iter=max_iter)
    run = Run(scenario, solver).with_output_dir(folder / "run")
    t0 = time.perf_counter()
    with (folder / "execution.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
        method = initialized_method(run)
        initial = method.get_density().copy()
        store = ResultStore(run.output.dir)
        try:
            iterations, stop = _loop(replace(run, output=replace(run.output, save_every=0)), method, store, None)
        finally:
            method.close()
        density = method.get_density().copy()
        fresh = method._model.evaluate(method.x, gradients=False)
        diag = []
        engine = getattr(method._model, "engine", None)
        if engine is not None:
            state = engine.solve(density)
            if hasattr(state, "T"):
                diag = np.sort(np.asarray(state.T)[:, 0]).tolist()
            elif hasattr(engine, "eigenvalues"):
                diag = np.sqrt(engine.eigenvalues(state, 3)).tolist()
            elif hasattr(engine, "buckling_factors"):
                diag = list(map(float, engine.buckling_factors(state, 0, 4)))
            if name == "harmonic":
                omega1 = np.sqrt(engine.eigenvalues(state, 1)[0])
                rows = [[w, float(engine.dynamic_compliance(state, 0, w))] for w in np.linspace(0., .9*omega1, 31)]
                np.savetxt(folder / "frequency-response.csv", rows, delimiter=",")
                static = float(np.dot(state.weights, state.compliances))
                checks["zero_frequency_static_relative_error"] = float(abs(rows[0][1]-static)/max(abs(static), 1e-30))
                checks["checks_passed"] &= checks["zero_frequency_static_relative_error"] < 1e-9
            if name == "multires":
                from toporia.plugins.physics.q4_plane_stress import solve_fea
                fine = float(solve_fea(method.problem, density, 3.)[2])
                checks["fine_q4_compliance"] = fine
                checks["coarse_over_fine_compliance"] = float(fresh.objective/fine)
        np.save(folder / "final-variables.npy", method.x, allow_pickle=False)
    checks.update(finite_execution=bool(np.isfinite(density).all() and np.isfinite(fresh.objective) and np.isfinite(store.objectives).all()),
                  bounded_density=bool(density.min() >= -1e-12 and density.max() <= 1+1e-12))
    checks["checks_passed"] = bool(checks["checks_passed"] and checks["finite_execution"] and checks["bounded_density"])
    report = dict(schema=1, case_id=name, preset_id=name, functions=list(CASES[name]["functions"]),
                  target=CASES[name]["target"], source_url=CASES[name]["source"], limitations=CASES[name]["limits"],
                  paper_status="paper_reproduction_to_fix", paper_visual_status="not_assessed", checks=checks,
                  iterations=iterations, stop_reason=stop, fresh_final_objective=float(fresh.objective),
                  last_recorded_objective=store.objectives[-1], physical_volume_fraction=float(density.mean()),
                  volume_limit=scenario.volfrac, feasible_volume_1e_4=bool(density.mean() <= scenario.volfrac+1e-4),
                  fresh_reported={k: float(v) for k, v in fresh.reported.items()},
                  constraints=[dict(name=c.name, value=float(c.value), exact=None if c.exact is None else float(c.exact)) for c in fresh.constraints],
                  feasible_constraints_1e_4=all((c.exact if c.exact is not None else c.value) <= 1e-4 for c in fresh.constraints),
                  scenario=to_dict(scenario), solver=to_dict(solver), resolved_method_params=type(method).resolve_params(solver),
                  versions=versions(), iteration_override=max_iter, runtime_seconds=time.perf_counter()-t0,
                  protocol="Existing engine loop; fresh final model evaluation after closing updater. Objective histories may be pre-update. Physical rows begin at y=0; 3D arrays are z,y,x. Diagnostic engine solves are additional to optimization. No source match implied.",
                  next_check="Align the identified research family with a numbered source panel, exact loads/supports, discretization and current formulation; see limitations.")
    np.save(folder / "initial-density.npy", initial, allow_pickle=False)
    np.save(folder / "final-density.npy", density, allow_pickle=False)
    np.savetxt(folder / "history.csv", np.column_stack([np.arange(1, iterations+1), store.objectives, store.volumes]), delimiter=",")
    dump(folder / "responses.json", store.responses)
    dump(folder / "report.json", report)
    (folder / "description.html").write_text(description_page(metadata(name)[0], description(name)), encoding="utf-8")
    fig, ax = figure_grid()
    field_plot(ax[0, 0], initial, "Initial physical field")
    field_plot(ax[0, 1], density, "Final physical field")
    ax[1, 0].plot(np.arange(1, iterations+1), store.objectives, label="Recorded objective")
    ax[1, 0].scatter([iterations], [fresh.objective], color="#c95735", label="Fresh final")
    if name == "multires":
        ax[1, 0].scatter([iterations], [checks["fine_q4_compliance"]], marker="x", color="#637d3f", label="Independent fine-Q4")
    ax[1, 0].set(xlabel="Engine step", ylabel="Objective (case-specific units)")
    ax[1, 0].legend(fontsize=8)
    if name == "harmonic":
        rows = np.loadtxt(folder / "frequency-response.csv", delimiter=",")
        ax[1, 1].plot(rows[:, 0], rows[:, 1], label="Undamped load-work amplitude")
        ax[1, 1].set(xlabel="Driving angular frequency (below first mode)", ylabel="Absolute F-transpose-u amplitude")
    elif (folder / "analytic-curve.csv").exists():
        rows = np.loadtxt(folder / "analytic-curve.csv", delimiter=",", ndmin=2)
        ax[1, 1].plot(rows[:, 0], rows[:, 1], "o-", label="Computed")
        ax[1, 1].plot(rows[:, 0], rows[:, 2], "--", label="Analytic reference")
        xlabel, ylabel = (("Cell spacing", "Planar interface energy") if name == "phase_field" else
                          ("Resolution (cells per length unit)", "First bending angular frequency") if name == "dynamic" else
                          ("Straight bar width (cells)", "Normalized length indicator") if name == "minimum_length" else
                          ("Resolution (cells per length unit)", "Maximum temperature"))
        ax[1, 1].set(xlabel=xlabel, ylabel=ylabel)
        if name in {"heat2d", "heat3d"}:
            ax[1, 1].set_ylim(0., 4.4)
            ax[1, 1].ticklabel_format(axis="y", style="plain", useOffset=False)
    elif diag:
        ax[1, 1].plot(diag, "o-", label="Final state diagnostic")
        ax[1, 1].set(xlabel="Sorted node index" if "heat" in name else "Mode index (0 based)",
                     ylabel="Temperature" if "heat" in name else "Critical load factor" if name == "buckling" else "Angular frequency")
    else:
        ax[1, 1].plot(store.volumes, label="Physical fraction")
        ax[1, 1].axhline(scenario.volfrac, color="#c95735", linestyle="--", label="Budget")
        ax[1, 1].set(xlabel="Engine step (0 based)", ylabel="Physical fraction")
    ax[1, 1].legend(fontsize=8)
    fig.suptitle(CASES[name]["label"]+" — bounded diagnostic", x=.05, ha="left")
    fig.text(.05, .025, "Paper reproduction unresolved. " + stop[:100], fontsize=8)
    fig.tight_layout(rect=(0, .06, 1, .95))
    fig.savefig(folder / "figure.png")
    return report


def post_cases(group, output):
    """One saved field, multiple operations; each retains a separate evidence record."""
    if group == "post2d":
        source = ROOT / "docs/research/evidence/batch3/mma/final-density.csv"
        field = np.loadtxt(source, delimiter=",")
    else:
        source = Path(output) / "solid3d/final-density.npy"
        if not source.exists():
            science_case("solid3d", output)
        field = np.load(source, allow_pickle=False)
    scenario, solver = recipe(group)
    if group == "post2d":
        solver = replace(solver, m=.5)
    problem = make_problem(scenario, solver.m)
    if field.shape != problem.shape:
        raise ValueError("Saved post-processing field does not match declared mesh")
    result = Result(field, problem, Run(scenario, solver), Path(output) / group / "exports")
    saved_history = ROOT / "docs/research/evidence/batch3/mma/history.csv"
    if group == "post2d":
        from matplotlib import pyplot as plt
        plt.switch_backend("Agg")  # export-only experiment; no desktop plotting window
        trace = np.loadtxt(saved_history, delimiter=",")
        result.history = dict(grey_level=trace[:, 3].tolist())
    records = []
    for name in (k for k in POSTS if (k == "export_stl") == (group == "post3d")):
        folder = Path(output) / name
        folder.mkdir(parents=True, exist_ok=True)
        result.folder = folder / "exports"
        result.files = []
        cls = POSTPROCESSORS.get(name)
        settings = dict(method="chaikin") if name == "smooth_outline" else {}
        part = cls(**resolve_params(name, cls.params, settings))
        metrics = part.process(result)
        metrics_finite = all(v is None or np.isfinite(v) for v in metrics.values())
        checks = dict(checks_passed=bool(metrics_finite), metrics_finite=bool(metrics_finite),
                      scope="Own engineering result/file check; not a source-paper or manufacturing certificate.")
        if name == "connectivity":
            # Separate flood fill, without scipy.ndimage or the plugin helper.
            solid = result.solid()
            labels = np.zeros(solid.shape, dtype=int)
            count = 0
            for start in np.ndindex(solid.shape):
                if not solid[start] or labels[start]:
                    continue
                count += 1
                stack = [start]
                labels[start] = count
                while stack:
                    y, x = stack.pop()
                    for yy, xx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                        if 0 <= yy < solid.shape[0] and 0 <= xx < solid.shape[1] and solid[yy, xx] and labels[yy, xx] == 0:
                            labels[yy, xx] = count
                            stack.append((yy, xx))
            def cells(nodes):
                return nodes[:-1, :-1] | nodes[1:, :-1] | nodes[:-1, 1:] | nodes[1:, 1:]
            supports = cells(problem.fixed_nodes | problem.fixed_x_nodes | problem.fixed_y_nodes)
            supported = set(labels[supports & solid]) - {0}
            floating = solid & ~np.isin(labels, list(supported))
            connected = all(bool((set(labels[cells(nodes) & solid])-{0}) & supported) for nodes in problem.load_node_sets)
            expected = dict(pieces=count, floating_fraction=float(floating.sum()/max(solid.sum(), 1)), loads_connected=connected)
            checks.update(independent_flood_fill=expected, checks_passed=all(metrics[k] == v for k, v in expected.items()))
        if name == "feature_size":
            calibration = []
            for width in (3, 6):
                bar = np.zeros_like(field)
                start = (bar.shape[0]-width)//2
                bar[start:start+width] = 1.
                measured = part.process(Result(bar, problem, result.run, result.folder))["min_member_mm"]
                calibration.append([width*problem.dy, measured])
            checks.update(straight_bar_width_calibration=calibration,
                          checks_passed=all(v is not None and abs(v-w) <= problem.dy+1e-9 for w, v in calibration))
        if name == "threshold":
            error = abs(float(result.binary.sum())-round(float(field.sum())))
            checks.update(integer_volume_error=error, checks_passed=error == 0.)
        if name == "grey_level":
            expected = float(100*np.mean(1-(2*field-1)**2))
            error = abs(metrics["final_pct"]-expected)
            checks.update(independent_grayness_error=error, checks_passed=error < 1e-10)
        if name == "export_svg":
            element = ET.parse(result.folder / "design.svg").getroot()
            checks.update(svg_root=element.tag, checks_passed=element.tag.endswith("svg"))
        if name in {"export_dxf", "smooth_outline"}:
            filename = "design_smooth.dxf" if name == "smooth_outline" else "design.dxf"
            text = (result.folder / filename).read_text(encoding="ascii")
            checks.update(closed_dxf_sections="EOF" in text and "ENDSEC" in text,
                          checks_passed="EOF" in text and "ENDSEC" in text)
        if name == "export_stl":
            data = (result.folder / "design.stl").read_bytes()
            n = struct.unpack_from("<I", data, 80)[0]
            triangles = np.array([struct.unpack_from("<9f", data, 84+50*i+12) for i in range(n)]).reshape(-1, 3, 3)
            signed = np.sum(np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])))/6
            expected = float(result.solid().sum()*problem.dx*problem.dy*problem.dz)
            checks.update(stl_byte_count_correct=len(data) == 84+50*n, oriented_mesh_volume=float(signed), voxel_volume=expected,
                          checks_passed=bool(len(data) == 84+50*n and abs(abs(signed)-expected) < 1e-5))
        report = dict(schema=1, case_id=name, preset_id=group, functions=["postprocessor:"+name],
                      target="Own engineering export/metric; source-inspired definitions do not identify a paper figure.",
                      source_url="", limitations=CASES[group]["limits"], paper_status=("not_applicable_engineering_demo" if name in {"connectivity", "export_svg", "export_dxf", "export_stl"} else "paper_reproduction_to_fix"),
                      paper_visual_status="not_assessed", checks=checks, metrics=metrics,
                      source_field=str(source.relative_to(ROOT) if source.is_relative_to(ROOT) else source),
                      source_field_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                      iterations=0, stop_reason="Saved field reused; no optimization", iteration_override=None,
                      next_check="Review the engineering invariant/file geometry separately from source-paper reconstruction; add independent calibration for measurements on curved or poorly resolved features.",
                      files=[p.name for p in result.files], settings=settings, scenario=to_dict(scenario), solver=to_dict(solver))
        if name == "grey_level":
            report.update(source_history=str(saved_history.relative_to(ROOT)), source_history_sha256=hashlib.sha256(saved_history.read_bytes()).hexdigest())
        dump(folder / "report.json", report)
        np.save(folder / "input-density.npy", field, allow_pickle=False)
        (folder / "description.html").write_text(description_page(metadata(group)[0], description(group)), encoding="utf-8")
        fig, ax = figure_grid()
        field_plot(ax[0, 0], field, "Saved physical density")
        field_plot(ax[0, 1], result.solid(), "Current binary interpretation")
        ax[1, 0].axis("off")
        ax[1, 0].text(.02, .95, json.dumps(metrics, indent=2)[:700], transform=ax[1, 0].transAxes, va="top", fontsize=9, family="monospace")
        if name == "grey_level":
            ax[1, 1].plot(100*np.asarray(result.history["grey_level"]))
            ax[1, 1].set(xlabel="Source run step (0 based)", ylabel="Non-discreteness (%)", title="Saved optimization history reused")
        else:
            ax[1, 1].axis("off")
            ax[1, 1].text(.02, .95, "Exports\n"+"\n".join(report["files"])+"\n\nSaved field reused\nNo optimization repeated", va="top", fontsize=10)
        fig.suptitle(name+" — saved-field engineering demonstration", x=.05, ha="left")
        fig.tight_layout(rect=(0, .02, 1, .95))
        fig.savefig(folder / "figure.png")
        records.append(report)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["all", *CASES], default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "results/research/batch4/generated")
    parser.add_argument("--strict-paper", action="store_true")
    args = parser.parse_args()
    failed = []
    for name in (CASES if args.case == "all" else [args.case]):
        try:
            reports = post_cases(name, args.output) if name.startswith("post") else [science_case(name, args.output)]
            for report in reports:
                print(report["case_id"], "checks", report["checks"]["checks_passed"], report["stop_reason"], flush=True)
                if not report["checks"]["checks_passed"] or (args.strict_paper and report["paper_status"] == "paper_reproduction_to_fix"):
                    failed.append(report["case_id"])
        except (ValueError, RuntimeError, ImportError, FloatingPointError) as error:
            folder = args.output / name
            folder.mkdir(parents=True, exist_ok=True)
            dump(folder / "execution-failure.json", dict(case_id=name, exception=type(error).__name__, message=str(error)))
            print(name, type(error).__name__, str(error), flush=True)
            failed.append(name)
    if failed:
        raise SystemExit("Failed/unresolved: " + ", ".join(failed))


if __name__ == "__main__":
    main()
