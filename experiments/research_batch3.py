"""Generate Batch 3 figures using the actual recipes and existing engine loop.

python -m experiments.research_batch3 [--case NAME] [--strict-paper]
Each result separates a finite execution, independent checks, feasibility and
paper reproduction. --strict-paper fails while any target remains unresolved.
"""

import argparse
import contextlib
import importlib.metadata
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import expit

from toporia.apps.research_render import description_page
from toporia.engine.loop import _loop, initialized_method
from toporia.engine.records import ResultStore
from toporia.framework.params import resolve_params
from toporia.framework.parts.model import Evaluation
from toporia.framework.problem.files import to_dict
from toporia.framework.problem.mesh import make_problem
from toporia.framework.problem.run import Run
from toporia.plugins.models.assembled import design_representation
from toporia.plugins.physics.q4_plane_stress import solve_fea
from toporia.plugins.problems._research_batch3 import CASES, description, metadata, recipe
from toporia.plugins.updaters import UPDATERS

ROOT = Path(__file__).resolve().parents[1]
NEXT_CHECKS = {
    "mma": "Recover a Svanberg numerical example with original bounds/initial values, then compare the local one-budget coefficients and asymptote history; the current MBB solve is only a diagnostic.",
    "pymoto_mma": "Use an identified MMA2007 reference example, not an assumed MMA1987 trajectory; align objective scaling and record every model evaluation.",
    "pymoto_gcmma": "Align a published conservative-approximation example and capture inner correction/trial counts as well as accepted steps.",
    "mmapy_mma": "Select a source-paper problem for the installed mmapy port, record its bounds/asymptote parameters and compare the complete trajectory.",
    "mmapy_gcmma": "Select a GCMMA conservative-correction example and compare inner trial evaluations, not only final MBB compliance.",
    "nlopt_mma": "Align an original MMA/CCSA source example with NLopt's safeguarded variant, tolerances and evaluation callback convention.",
    "conlin": "Recover Fleury-Braibant geometry, constraint normalization and initial point, then compare reciprocal approximations and the multiplier solve.",
    "oc_multi": "First establish feasibility for the selected stress limit and distributed-load mesh. The recorded point-load companion violates stress despite meeting volume; then align an original multi-OC example.",
    "beso": "Recover a numbered Huang-Xie beam example and align history smoothing, evolution rate, addition cap, discrete ties and the physical-volume convention.",
    "beso_hard": "Recover a hard-kill source example and distinguish exact design removal from the remaining ersatz stiffness, then align neighbor-sensitivity reintroduction.",
    "floating_projection": "Align a numbered FPTO panel, filter placement, move .02, threshold root and complete beta continuation; the 120-step companion has not established a source match.",
    "simpl": "Recover explicit source schematic coordinates or retain the plot as a controlled equation instance. A source optimization match separately needs the SiMPL-A/B step policy and gradient discretization.",
    "adam": "Use original Figure 1 task/data and stochastic gradients for an Adam paper comparison. The deterministic moment probe certifies neither that figure nor topology-specific AL feasibility.",
    "pto": "Inspect the native 120x40 Figure 3 attempt. An exact PTOc reproduction would need a separately declared element-compliance allocation and filtered redistribution variant, not retuning this sensitivity proxy.",
    "tobs": "Recover TOBS101 panel inputs, switching relaxation and integer-solve tolerances; compare true physical constraint residuals after each MILP update.",
    "augmented_lagrangian": "Establish a feasible local-stress benchmark with aligned stress relaxation, mesh/load support and multiplier update schedule before comparing a PolyStress panel.",
    "scipy_slsqp": "Recover a Kraft numerical example and align normalization, bound handling, tolerances and accepted-iterate callbacks.",
    "nlopt_slsqp": "Use the same identified Kraft problem as SciPy and compare accepted steps separately from NLopt objective evaluations.",
    "scipy_trust_constr": "Choose an identified trust-region/interior-point reference example and align SR1 versus BFGS, scaling, radius and barrier stopping criteria.",
    "nlopt_ccsaq": "Recover a Svanberg conservative-separable quadratic example and align rho safeguards and actual trial/evaluation counts.",
    "nlopt_auglag": "Choose an identified constrained source example and align the outer multiplier and inner L-BFGS budgets; a library FTOL flag alone is insufficient.",
    "nullspace": "Recover a Feppon active-constraint example and match metric, tangent/restoration gains and bound retraction rather than treating this coarse MBB solve as a shape benchmark.",
    "mmc": "Recover Figure 8's geometry/field normalization or keep this as an own instance. A final-design comparison also needs the reference maximum union, projection and analysis sampling aligned.",
    "mmc_variable": "Recover a numbered variable-thickness MMC panel and thickness ordering, then align union, Heaviside sampling and optimizer settings with MMC188.",
    "mmv": "A 2017-source reproduction needs 3D B-spline void surfaces and DOF-removal support. Keep the 2D superellipse example explicitly separate until that algorithm is implemented.",
    "bspline": "Recover Qian's numbered example with exact knot vector, coefficient grid, density constraints, FE mesh and stopping rule before comparing optimized shapes.",
    "geometry_projection": "Align a GPTO source example including radius variables, penalized per-bar field and p-norm union. Preserve the independently verified inside-positive cap integral separately.",
    "neural": "Align a numbered TOuNN panel and its LeakyReLU/batch-normalization/AMSGrad architecture. The present tanh/Adam-AL run remains gray and is not that algorithm.",
    "levelset": "Compare against a source TOPRBF panel with its median normalization and original rescaling; the mean-normalized clipped variant cannot be called an exact port.",
    "levelset_hamilton_jacobi": "Recover a Challis panel and align velocity sign/scale, boundary and topological-derivative conventions, nucleation and volume feedback.",
    "levelset_reaction_diffusion": "Recover a levelset88 panel and align nodal discretization, Heaviside, reaction/diffusion scaling and original AL volume feedback rather than the current bisection.",
}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def representation_probe(case_id, folder):
    """Independent directional checks at a perturbed, interior design.

    Five deterministic directions detect missing terms, signs and ordering;
    this does not certify derivatives at switches, ties or saturated bounds.
    """
    scenario, solver = recipe(case_id)
    problem = make_problem(scenario, solver.m)
    operator = design_representation(solver)
    operator.setup(problem)
    rng = np.random.default_rng(3022)
    z = operator.initial()
    lower, upper = operator.bounds()
    z = np.clip(z + .015 * rng.normal(size=z.shape), lower + 1e-4, upper - 1e-4)
    sensitivity = rng.normal(size=problem.shape)
    gradient = operator.backward(z, sensitivity)
    errors = []
    for _ in range(5):
        direction = rng.normal(size=z.shape)
        direction /= np.linalg.norm(direction)
        h = 1e-6
        fd = np.sum(sensitivity * (operator.density(z+h*direction)-operator.density(z-h*direction))) / (2*h)
        adjoint = np.sum(gradient * direction)
        errors.append(float(abs(fd-adjoint)/max(1., abs(fd), abs(adjoint))))
    field = operator.density(z)
    np.savetxt(folder / "probe-density.csv", field, delimiter=",")
    np.savetxt(folder / "probe-variables.csv", z.reshape(-1), delimiter=",")
    checks = dict(directional_adjoint_errors=errors, adjoint_tolerance=2e-5,
                  checks_passed=bool(max(errors) < 2e-5 and np.isfinite(field).all()
                                     and field.min() >= -1e-12 and field.max() <= 1+1e-12),
                  scope="Five smooth-field directions; no certification at topology switches or bounds.")
    if case_id == "bspline":
        # Independent scalar Cox-de Boor recursion, rather than SciPy BSpline.
        def basis(i, p, x, knots):
            if p == 0:
                return float(knots[i] <= x < knots[i+1])
            a, b = knots[i+p]-knots[i], knots[i+p+1]-knots[i+1]
            return ((x-knots[i])/a*basis(i, p-1, x, knots) if a else 0.) + (
                (knots[i+p+1]-x)/b*basis(i+1, p-1, x, knots) if b else 0.)
        matrices = []
        for n, c in zip(problem.shape, (4, 8), strict=True):
            knots = [0.]*4 + [i/(c-3) for i in range(1, c-3)] + [1.]*4
            matrices.append(np.array([[basis(j, 3, (i+.5)/n, knots) for j in range(c)] for i in range(n)]))
        expected = matrices[0] @ z.reshape(4, 8) @ matrices[1].T
        error = float(np.max(np.abs(field-expected)))
        checks.update(independent_cox_de_boor_max_error=error,
                      partition_of_unity_max_error=float(max(np.max(abs(m.sum(axis=1)-1)) for m in matrices)))
        checks["checks_passed"] &= error < 1e-12
    return checks


class BudgetProbe:
    """An explicitly diagnostic model, not a published optimization problem."""
    volume_limit = 100.

    def bounds(self):
        return np.full(2, -10.), np.full(2, 10.)

    def volume_of(self, z):
        return float(np.sum(z))


def update_probe(case_id, folder):
    if case_id == "adam":
        settings = resolve_params("adam", UPDATERS.get("adam").params,
                                  dict(lr=.01, lr_decay=1., beta1=.9, beta2=.999, multiplier=False))
        updater = UPDATERS.get("adam")()
        updater.initialize(BudgetProbe(), settings)
        actual, expected = np.array([.2, .6]), np.array([.2, .6])
        first, second = np.zeros(2), np.zeros(2)
        errors, rows = [], []
        for t in range(1, 21):
            gradient = np.array([np.sin(t*.7), np.cos(t*.3)])
            evaluation = Evaluation(1., gradient, 0., np.zeros(2))
            actual = updater.update(actual, evaluation, t-1)
            first = .9*first + .1*gradient
            second = .999*second + .001*gradient**2
            expected -= .01*(first/(1-.9**t))/(np.sqrt(second/(1-.999**t))+1e-8)
            errors.append(float(np.max(abs(actual-expected))))
            rows.append([t, *actual, *expected])
        np.savetxt(folder / "adam-recurrence.csv", rows, delimiter=",", header="step,actual0,actual1,reference0,reference1")
        return dict(checks_passed=max(errors) < 1e-13, adam_algorithm1_max_error=max(errors),
                    scope="Independent Algorithm 1 recurrence; fixed deterministic gradient stream, inactive budget, no learning-rate decay or active bounds. Not Figure 1 training curves.")
    if case_id == "simpl":
        model = BudgetProbe()
        model.volume_limit = 1.
        model.bounds = lambda: (np.full(2, 1e-9), np.ones(2))
        updater = UPDATERS.get("simpl")()
        updater.initialize(model, resolve_params("simpl", updater.params, {}))
        x, d = np.array([.3, .5]), np.array([-1., -2.])
        latent = np.log(x/(1-x))
        uncorrected = expit(latent-d/2)
        multiplier = brentq(lambda lam: np.sum(expit(latent-d/2-lam))-1., 0., 10., xtol=1e-14)
        reference = expit(latent-d/2-multiplier)
        actual = updater.update(x, Evaluation(1., d, float(x.sum()), np.ones(2)), 0)
        error = float(np.max(abs(actual-reference)))
        dump(folder / "primal-latent.json", dict(initial=x.tolist(), latent=latent.tolist(),
             uncorrected=uncorrected.tolist(), multiplier=multiplier, expected=reference.tolist(), actual=actual.tolist()))
        return dict(checks_passed=error < 1e-9, independent_multiplier_max_error=error,
                    scope="Source Fig. 1 construction with explicitly own coordinates; equation-instance check, not digitized source coordinates or optimization histories.")
    return dict(checks_passed=True, scope="Execution and final-field checks below; no independent updater-algorithm reference for this case.")


def cap_probe(folder):
    from toporia.plugins.representations.geometry_projection import cap_projection
    t = np.linspace(-1., 1., 101)
    actual2, _ = cap_projection(t, 1., 2)
    actual3, _ = cap_projection(t, 1., 3)
    # Integrate cross sections of the unit disk / sphere to the cut coordinate.
    exact2 = np.array([quad(lambda s: 2*np.sqrt(max(0., 1-s*s))/np.pi, -1., x,
                            epsabs=1e-12, epsrel=1e-12)[0] for x in t])
    exact3 = np.array([quad(lambda s: .75*(1-s*s), -1., x)[0] for x in t])
    np.savetxt(folder / "cap-quadrature.csv", np.column_stack([t, actual2, exact2, actual3, exact3]),
               delimiter=",", header="distance,computed2,quadrature2,computed3,quadrature3")
    error = float(max(np.max(abs(actual2-exact2)), np.max(abs(actual3-exact3))))
    return dict(cap_quadrature_max_error=error, cap_quadrature_pass=error < 1e-10)


def plot_case(case_id, folder, initial, density, store, report):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    fig = Figure(figsize=(11, 7), dpi=150, facecolor="white")
    FigureCanvasAgg(fig)
    axes = fig.subplots(2, 2)
    for ax, field, title in ((axes[0, 0], initial, "Initial physical field"), (axes[0, 1], density, "Final physical field")):
        ax.imshow(field, origin="lower", cmap="gray_r", vmin=0, vmax=1, extent=(0, 60, 0, 20), interpolation="nearest")
        ax.set(title=title, xlabel="x (mm)", ylabel="y (mm)")
    steps = np.arange(1, len(store.objectives)+1)
    axes[1, 0].semilogy(steps, store.objectives, color="#1d628c", label="Recorded objective")
    axes[1, 0].scatter([steps[-1]], [report["fresh_final_compliance"]], color="#c95735", zorder=3, label="Fresh final compliance")
    axes[1, 0].set(xlabel="Displayed engine step (not physics solves)", ylabel="Compliance (normalized units)")
    axes[1, 0].legend(fontsize=8)
    axes[1, 0].grid(alpha=.2)
    right = axes[1, 1]
    if case_id == "geometry_projection":
        curves = np.loadtxt(folder / "cap-quadrature.csv", delimiter=",")
        right.plot(curves[:, 0], curves[:, 1], label="2D cap")
        right.plot(curves[:, 0], curves[:, 3], label="3D cap")
        right.scatter(curves[::10, 0], curves[::10, 2], s=12, label="Independent quadrature")
        right.set(xlabel="Inside-positive distance / window", ylabel="Local cap fraction")
    elif case_id == "simpl":
        data = json.loads((folder / "primal-latent.json").read_text())
        pts = np.array([data["initial"], data["uncorrected"], data["actual"]])
        start = np.array(data["latent"])
        trial = np.log(pts[1]/(1-pts[1]))
        s = np.linspace(0., 1., 101)[:, None]
        gradient_path = expit(start+s*(trial-start))
        correction_path = expit(trial-s*data["multiplier"])
        right.plot(gradient_path[:, 0], gradient_path[:, 1], label="Latent gradient path")
        right.plot(correction_path[:, 0], correction_path[:, 1], label="Latent volume correction")
        right.scatter(pts[:, 0], pts[:, 1], s=24, color="#1d628c")
        right.plot([0, 1], [1, 0], "k--", label="Volume boundary")
        for point, label in zip(pts, ("Start", "Gradient", "Corrected"), strict=True):
            right.annotate(label, point, xytext=(6, 7), textcoords="offset points", fontsize=8)
        right.set(xlim=(0, 1), ylim=(0, 1), xlabel="Density 1", ylabel="Density 2")
    else:
        right.plot(steps, store.volumes, label="Physical fraction", color="#1d628c")
        right.axhline(.5, color="#c95735", linestyle="--", label="Budget")
        right.plot(steps, store.grey_levels, label="Mean 4 rho(1-rho)", color="#637d3f", alpha=.8)
        right.set(xlabel="Displayed engine step", ylabel="Fraction / grayness")
    right.legend(fontsize=8)
    right.grid(alpha=.2)
    fig.suptitle(CASES[case_id]["label"] + " — bounded diagnostic", x=.05, ha="left", fontsize=14)
    fig.text(.05, .035, "Paper comparison unresolved. " + report["stop_reason"][:95], fontsize=9)
    fig.tight_layout(rect=(.02, .07, .98, .94))
    fig.savefig(folder / "figure.png", dpi=150)


def versions():
    result = dict(python=platform.python_version())
    for package in ("numpy", "scipy", "matplotlib", "pymoto", "mmapy", "nlopt", "nullspace_optimizer"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = "distribution version unavailable"
    return result


def run_case(case_id, output, max_iter=None):
    """Run one actual recipe. The optional iteration override is diagnostic only."""
    from dataclasses import replace
    data = CASES[case_id]
    folder = Path(output) / case_id
    folder.mkdir(parents=True, exist_ok=True)
    scenario, solver = recipe(case_id)
    if max_iter is not None:
        solver = replace(solver, max_iter=max_iter)
    run = Run(scenario, solver).with_output_dir(folder / "run")
    run = replace(run, output=replace(run.output, save_every=0))
    checks = representation_probe(case_id, folder) if data["function"].startswith("representation:") else update_probe(case_id, folder)
    if case_id == "geometry_projection":
        checks.update(cap_probe(folder))
        checks["checks_passed"] &= checks["cap_quadrature_pass"]
    t0 = time.perf_counter()
    with (folder / "execution.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
        method = initialized_method(run)
        store = ResultStore(run.output.dir)
        initial = method.get_density().copy()
        try:
            iteration, stop_reason = _loop(run, method, store, None)
        finally:
            method.close()
        density = method.get_density().copy()
        optimizer = method.report()
        solves = method.get_responses().get("solves")
        extra = {}
        if hasattr(method, "_model"):
            fresh = method._model.evaluate(method.x, gradients=False)
            final_compliance = float(fresh.objective)
            extra = dict(fresh_reported={k: float(v) for k, v in fresh.reported.items()},
                         fresh_constraints=[dict(name=c.name, value=float(c.value),
                                                 exact=float(c.exact) if c.exact is not None else None) for c in fresh.constraints])
            extra["fresh_constraints_feasible_1e_4"] = all(
                (c.exact if c.exact is not None else c.value) <= 1e-4 for c in fresh.constraints)
            # Include raw variables so geometry and network runs can be resumed/reviewed.
            np.savetxt(folder / "final-variables.csv", method.x.reshape(-1), delimiter=",")
        else:
            # Own level-set methods all use p=1 ersatz stiffness and no filter.
            final_compliance = float(solve_fea(method.problem, density, penal=1.)[2])
        store.save_final(density, save_history=False)
    finite = bool(np.isfinite(density).all() and np.isfinite(store.objectives).all() and np.isfinite(final_compliance))
    bounded = bool(density.min() >= -1e-12 and density.max() <= 1+1e-12)
    checks.update(finite_execution=finite, bounded_density=bounded,
                  checks_passed=bool(checks["checks_passed"] and finite and bounded))
    report = dict(schema=1, case_id=case_id, functions=[data["function"]],
                  source_url=data["source"], target=data["target"], limitations=data["limits"],
                  paper_status="paper_reproduction_to_fix", paper_visual_status="not_assessed",
                  checks=checks, iterations=iteration, stop_reason=stop_reason, optimizer=optimizer,
                  fresh_final_compliance=final_compliance, last_recorded_objective=store.objectives[-1],
                  physical_volume_fraction=float(density.mean()), volume_excess=float(density.mean()-scenario.volfrac),
                  feasible_volume_1e_4=bool(density.mean() <= scenario.volfrac+1e-4),
                  grayness=float(np.mean(4*density*(1-density))), engine_physics_evaluations_before_final_check=solves,
                  final_check_extra_model_evaluations=1, runtime_seconds=time.perf_counter()-t0,
                  captured_at=datetime.now(timezone.utc).isoformat(), versions=versions(),
                  protocol="Unmodified recipe and existing engine _loop; final re-evaluation after optimizer close. "
                           "Density rows start at physical y=0. Objective histories may be pre-update; volume is displayed post-update. "
                           "An execution pass does not mean feasibility, convergence or paper agreement.",
                  iteration_override=max_iter, next_check=NEXT_CHECKS[case_id],
                  scenario=to_dict(scenario), solver=to_dict(solver), resolved_method_params=type(method).resolve_params(solver),
                  **extra)
    np.savetxt(folder / "initial-density.csv", initial, delimiter=",")
    np.savetxt(folder / "final-density.csv", density, delimiter=",")
    np.savetxt(folder / "history.csv", np.column_stack([np.arange(1, iteration+1), store.objectives, store.volumes, store.grey_levels]),
               delimiter=",", header="displayed_step,recorded_objective,post_update_fraction,grayness")
    dump(folder / "responses.json", store.responses)
    dump(folder / "report.json", report)
    (folder / "description.html").write_text(description_page(metadata(case_id)[0], description(case_id)), encoding="utf-8")
    (folder / "TO-FIX.md").write_text(data["limits"] + "\n\n" + report["next_check"] + "\n", encoding="utf-8")
    plot_case(case_id, folder, initial, density, store, report)
    (folder / "execution-failure.json").unlink(missing_ok=True)
    return report


def render_case(case_id, output):
    """Re-render an existing recorded execution. Never presented as a fresh solve."""
    folder = Path(output) / case_id
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    if report["case_id"] != case_id:
        raise ValueError("Recorded case identity differs")
    history = np.loadtxt(folder / "history.csv", delimiter=",", ndmin=2)
    if len(history) != report["iterations"]:
        raise ValueError("History length differs from recorded execution")
    store = ResultStore(folder / "run")
    store.objectives, store.volumes, store.grey_levels = (history[:, i].tolist() for i in (1, 2, 3))
    initial = np.loadtxt(folder / "initial-density.csv", delimiter=",", ndmin=2)
    density = np.loadtxt(folder / "final-density.csv", delimiter=",", ndmin=2)
    (folder / "description.html").write_text(description_page(metadata(case_id)[0], description(case_id)), encoding="utf-8")
    plot_case(case_id, folder, initial, density, store, report)
    (folder / "execution-failure.json").unlink(missing_ok=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["all", *CASES], default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "results/research/batch3/generated")
    parser.add_argument("--strict-paper", action="store_true")
    parser.add_argument("--render-only", action="store_true", help="Re-render existing reports/fields; does not run physics")
    args = parser.parse_args()
    failed = []
    for case_id in (CASES if args.case == "all" else [args.case]):
        try:
            report = render_case(case_id, args.output) if args.render_only else run_case(case_id, args.output)
            print(case_id, "checks", report["checks"]["checks_passed"], "steps", report["iterations"],
                  "final C", round(report["fresh_final_compliance"], 4), "fraction", round(report["physical_volume_fraction"], 6), flush=True)
            if not report["checks"]["checks_passed"] or args.strict_paper:
                failed.append(case_id)
        except (ImportError, ValueError, RuntimeError, FloatingPointError) as error:
            folder = args.output / case_id
            folder.mkdir(parents=True, exist_ok=True)
            dump(folder / "execution-failure.json", dict(case_id=case_id, exception=type(error).__name__, message=str(error)))
            print(case_id, type(error).__name__, str(error), flush=True)
            failed.append(case_id)
    if failed:
        raise SystemExit("Unresolved/failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
