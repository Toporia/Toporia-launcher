"""Batch 2 figures, independent checks and explicit unresolved-paper records.

python -m experiments.research_batch2
python -m experiments.research_batch2 --case sinh
python -m experiments.research_batch2 --companions

Default writes to ignored results/research/batch2/generated. Successful
engineering checks never imply a paper match. --strict-paper exits nonzero
while any selected paper target remains unresolved.
"""

import argparse
import contextlib
import json
from datetime import datetime, timezone
from fractions import Fraction
from io import StringIO
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.special import expit

from toporia.apps.research_render import description_page
from toporia.framework.params import resolve_params
from toporia.framework.problem.mesh import make_problem
from toporia.framework.problem.run import Run
from toporia.plugins.filters import FILTERS
from toporia.plugins.interpolations import INTERPOLATIONS
from toporia.plugins.problems._research_batch2 import CASES, QUARANTINED, description, metadata, recipe
from toporia.plugins.schedules import SCHEDULES

ROOT = Path(__file__).resolve().parents[1]
PDE_REFERENCE = ROOT / "tests/references/paper_top82.json"
CURVE_MATCHES = {"sinh", "hashin_shtrikman", "ordered_simp"}
NEXT_CHECKS = {
    "pde_anisotropic": "Select a published directional FV example or establish this as an explicitly independent extension; the cosine verification already passes.",
    "heaviside": "Obtain the Figure 5 source bitmap and exact filtering settings; do not substitute the diagnostic ramp for the paper pattern.",
    "heaviside_volume": "The 0/1-design limit is settled (identity when uniform, explicit error when mixed). Align a numbered top99neo source figure and compare its threshold history.",
    "morphology": "Recover Figure 3's bitmap and five-cell structuring element; compare the uniform-weight hard limit separately from finite-beta cone weighting.",
    "am": "Align an identified Langelaar source panel and input geometry with the build direction and tiny shift/backshift conventions.",
    "symmetry": "Select an identifiable research example for the symmetry restriction, or classify this Toporia operator as an engineering demonstration.",
    "routing": "Choose a research reference for the current normalized p-norm/interior-mask router rule; it is not the paper's exponential morphology operator.",
    "extrusion": "Recover the 3-D paper geometry, loads and optimized panel; the 2-D mean projector is already independently checked.",
    "pattern": "Recover the paper's repeating-cell geometry, boundary conditions and target panel; repeated diagnostic cells alone are insufficient.",
    "casting": "Resolve the formulation difference: source Heaviside casting parameterization versus the current smooth cumulative minimum.",
    "machining": "Use the paper's exact example and boundary conventions; separate Cartesian ideal-tool agreement from finite cutter/holder claims.",
    "self_support": "Align nodal versus cell-centred design points and threshold calibration on a named source example before comparing final topologies.",
    "ramp": "Obtain the original paper's numbered figure and parameter values; do not attribute the diagnostic q grid to that figure.",
    "schedule_steps": "Recover a paper iteration history and exact continuation settings; the own fixed-step clock is not such a history.",
    "schedule_geometric": "Match the paper's optimizer and early-convergence trigger as well as its 50-step clock; the bounded OC companion is not converged.",
    "schedule_linear": "Select a defensible research application or retain this as an explicitly original engineering ramp; no originating paper is claimed.",
    "schedule_settled": "Recover actual paper design-change observations and trigger settings; synthetic rule agreement and an unconverged OC companion are insufficient.",
    "ordered_simp": "Current attribution is corrected to the 2022 modified law. Reproducing the distinct original 2017 formula would need a separately declared variant, not an undocumented algorithm change.",
}


def _figure(rows=1, columns=1, width=11, height=4):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    figure = Figure(figsize=(width, height), dpi=150, facecolor="white")
    FigureCanvasAgg(figure)
    axes = np.asarray(figure.subplots(rows, columns, squeeze=False))
    return figure, axes


def _finish(figure, case_id, folder):
    case = CASES[case_id]
    figure.suptitle(case["label"], fontsize=14, x=.06, ha="left")
    figure.text(.06, .015, case["target"][:150], fontsize=8)
    figure.tight_layout(rect=(.02, .06, .98, .91))
    figure.savefig(folder / "figure.png", dpi=150)


def _filter(spec, problem, solver):
    values = dict(spec)
    cls = FILTERS.get(values.pop("type"))
    operator = cls(**resolve_params(cls.name, cls.params, values))
    operator.setup(problem, solver)
    operator.step(100)  # routing ramp fully active; other selected filters are fixed
    return operator


def _adjoint_check(operator, shape):
    """Differentiate a separate smooth field, avoiding binary switches/ties."""
    rng = np.random.default_rng(2202)
    x = .2 + .6 * rng.random(shape)
    direction = rng.normal(size=shape)
    direction /= np.linalg.norm(direction)
    weights = rng.normal(size=shape)
    operator.forward(x)
    actual = float(np.sum(operator.backward(x, weights) * direction))
    h = 1e-6
    high = float(np.sum(operator.forward(x + h * direction) * weights))
    low = float(np.sum(operator.forward(x - h * direction) * weights))
    expected = (high - low) / (2 * h)
    error = abs(actual - expected) / max(1., abs(actual), abs(expected))
    return {"directional_adjoint_error": error, "adjoint_tolerance": 2e-5,
            "adjoint_scope": "ordinary backward on a separate smooth 0.2-to-0.8 field; not a certificate at binary switches or for backward_volume overrides",
            "adjoint_pass": bool(error <= 2e-5)}


def pattern(shape):
    """Own diagnostic bitmap, expressed in physical bottom-up array coordinates."""
    field = np.zeros(shape)
    field[:3, :] = 1.
    field[3:14, 8:12] = 1.
    field[12:15, 8:30] = 1.
    field[16:19, 44:54] = 1.
    field[4:12, 35:58] = 1.
    field[6:10, 40:42] = 0.
    field[6:10, 47:53] = 0.
    return field


def field_figure(case_id, folder):
    case = CASES[case_id]
    scenario, solver = recipe(case_id, showcase=False)
    problem = make_problem(scenario, 1.)
    x = pattern(problem.shape)
    report = {"input_origin": "own controlled bitmap, row 0 at physical y=0",
              "shape": list(x.shape), "input_mean": float(x.mean())}
    if case_id == "pde_anisotropic":
        y, z = np.indices(problem.shape)
        mode = np.cos(np.pi * (z + .5) / problem.nelx) * np.cos(np.pi * (y + .5) / problem.nely)
        x = .5 + .4 * mode
        operator = _filter(case["spec"], problem, solver)
        output = operator.forward(x)
        discrete_eigenvalue = 1 + 6.**2 / 12 * 4 * np.sin(np.pi / (2 * problem.nelx))**2 + (
            2.**2 / 12 * 4 * np.sin(np.pi / (2 * problem.nely))**2)
        expected = .5 + .4 * mode / discrete_eigenvalue
        continuous = .5 + .4 * mode / (1 + 6.**2 / 12 * (np.pi / problem.nelx)**2 +
                                      2.**2 / 12 * (np.pi / problem.nely)**2)
        error = float(np.max(abs(output - expected)))
        report.update(input_origin="cell-centre Neumann cosine mode, not a paper bitmap",
                      discrete_cosine_error=error, discrete_tolerance=1e-12,
                      continuous_discretization_error=float(np.max(abs(output - continuous))))
        fields = [(x, "Cosine input"), (output, "Directional FV solution"), (abs(output - expected), "Absolute analytic discrete error")]
        report["checks_passed"] = error < 1e-12
    elif case_id == "morphology":
        fields = [(x, "Own input, not the paper bitmap")]
        checks = []
        for mode in ("erode", "dilate", "open", "close"):
            operator = _filter({**case["spec"], "mode": mode}, problem, solver)
            output = operator.forward(x)
            fields.append((output, mode.capitalize()))
            checks.append(_adjoint_check(operator, x.shape))
        report.update(operation_checks=checks, checks_passed=all(item["adjoint_pass"] for item in checks))
        fields.append((abs(fields[2][0] - fields[1][0]), "Dilate minus erode"))
    else:
        operator = _filter(case["spec"], problem, solver)
        output = operator.forward(x)
        fields = [(x, "Own controlled input"), (output, "Implemented output"),
                  ((output >= .5).astype(float), "Threshold diagnostic only")]
        independent = {}
        if case_id == "symmetry":
            expected = (x + x[::-1] + x[:, ::-1] + x[::-1, ::-1]) / 4
            independent["projector_error"] = float(np.max(abs(output - expected)))
        elif case_id == "extrusion":
            expected = np.tile(np.sum(x, axis=0) / x.shape[0], (x.shape[0], 1))
            independent["projector_error"] = float(np.max(abs(output - expected)))
        elif case_id == "pattern":
            expected = np.zeros_like(x)
            cell_y, cell_x = x.shape[0] // 2, x.shape[1] // 3
            for iy in range(cell_y):
                for ix in range(cell_x):
                    mean = sum(x[iy + a * cell_y, ix + b * cell_x] for a in range(2) for b in range(3)) / 6
                    expected[iy::cell_y, ix::cell_x] = mean
            independent["projector_error"] = float(np.max(abs(output - expected)))
        elif case_id == "casting":
            # A corrected smooth minimum can increase by at most sqrt(eps)/2.
            independent["max_increase_along_draw"] = float(np.max(np.diff(output, axis=0)))
            independent["monotonicity_tolerance"] = 5.000001e-4
        if "projector_error" in independent:
            fields[2] = (abs(output - expected), "Absolute independent projector error")
            independent["idempotence_error"] = float(np.max(abs(operator.forward(output) - output)))
            independent["mean_error"] = float(abs(output.mean() - x.mean()))
        report.update(independent, **_adjoint_check(operator, x.shape))
        report["checks_passed"] = report["adjoint_pass"] and independent.get("projector_error", 0.) < 1e-12
        if case_id == "casting":
            report["checks_passed"] &= independent["max_increase_along_draw"] <= independent["monotonicity_tolerance"]
    report["output_mean"] = float(output.mean())
    report["output_range"] = [float(np.min(output)), float(np.max(output))]
    np.savetxt(folder / "input.csv", x, delimiter=",")
    np.savetxt(folder / "output.csv", output, delimiter=",")
    nrows = 2 if len(fields) > 3 else 1
    figure, axes = _figure(nrows, 3, height=6 if nrows == 2 else 3.6)
    for axis, (field, title) in zip(axes.flat, fields, strict=True):
        kwargs = {"cmap": "magma"} if "error" in title.lower() else {"cmap": "gray_r", "vmin": 0, "vmax": 1}
        shown = axis.imshow(field, origin="lower", interpolation="nearest", **kwargs)
        axis.set_title(title, fontsize=10)
        axis.set_xlabel("x cell index")
        axis.set_ylabel("y cell index")
        if "error" in title.lower():
            figure.colorbar(shown, ax=axis, fraction=.04)
    _finish(figure, case_id, folder)
    return report


def projection_figure(case_id, folder):
    case = CASES[case_id]
    scenario, solver = recipe(case_id, showcase=False)
    problem = make_problem(scenario, 1.)
    x = np.linspace(0, 1, 201).reshape(1, -1)
    figure, axes = _figure(1, 2, height=4.3)
    if case_id == "heaviside":
        errors, columns = [], [x.ravel()]
        for beta in (1., 2., 4., 8., 16., 32.):
            operator = _filter({**case["spec"], "beta": beta, "beta_max": beta}, problem, solver)
            actual = operator.forward(x)
            a, b = expit(-beta), expit(beta)
            expected = (expit(2 * beta * (x - .5)) - a) / (b - a)
            errors.append(float(np.max(abs(actual - expected))))
            columns.append(actual.ravel())
            axes[0, 0].plot(x.ravel(), actual.ravel(), label=f"beta={beta:g}")
        check = _adjoint_check(operator, problem.shape)
        report = {**check, "equivalent_logistic_error": max(errors), "equation_tolerance": 1e-12}
        report["checks_passed"] = check["adjoint_pass"] and max(errors) <= 1e-12
        axes[0, 1].plot(x.ravel(), operator.backward(x, np.ones_like(x)).ravel(), color="#245c7e")
        axes[0, 1].set_ylabel("Derivative at beta=32")
        axes[0, 0].set_ylabel("Projected density")
        np.savetxt(folder / "curves.csv", np.column_stack(columns), delimiter=",",
                   header="input,beta1,beta2,beta4,beta8,beta16,beta32", comments="")
    else:
        source = x**2
        operator = _filter(case["spec"], problem, solver)
        actual = operator.forward(source)
        fixed = _filter({**case["spec"], "eta_mode": "fixed", "eta": .5}, problem, solver).forward(source)
        # Independent root finder rather than the implementation's bisection.
        def projected(eta):
            lo = expit(-32 * eta)
            hi = expit(32 * (1 - eta))
            return (expit(32 * (source - eta)) - lo) / (hi - lo)
        eta = brentq(lambda e: float(projected(e).mean() - source.mean()), 0., 1., xtol=1e-14)
        error = float(np.max(abs(actual - projected(eta))))
        report = {**_adjoint_check(operator, problem.shape), "independent_root_eta": float(eta),
                  "root_field_error": error, "preserved_mean_error": float(abs(actual.mean() - source.mean()))}
        report["checks_passed"] = report["adjoint_pass"] and error < 1e-11 and report["preserved_mean_error"] < 1e-12
        # At an all-solid design every threshold preserves the volume; the derivative is the identity
        # limit. Check it against one-sided finite differences in random inward directions.
        saturated = np.ones(problem.shape)
        seed = np.random.default_rng(3).standard_normal(problem.shape)
        operator.forward(saturated)
        saturated_adjoint = operator.backward(saturated, seed)
        base, step, worst = float(np.sum(seed * operator.forward(saturated))), 1e-7, 0.0
        for k in range(4):
            direction = -np.abs(np.random.default_rng(10 + k).standard_normal(problem.shape))
            slope = (float(np.sum(seed * operator.forward(saturated + step * direction))) - base) / step
            worst = max(worst, abs(slope - float(np.sum(saturated_adjoint * direction))) / max(1.0, abs(slope)))
        mixed = np.ones(problem.shape)
        mixed[:, : problem.shape[1] // 2] = 0.0
        operator.forward(mixed)
        try:
            operator.backward(mixed, seed)
            mixed_refused = False
        except ValueError:
            mixed_refused = True
        report["saturation_probe"] = {
            "all_solid_adjoint_finite": bool(np.all(np.isfinite(saturated_adjoint))),
            "all_solid_identity_fd_error": worst, "mixed_binary_refused": mixed_refused,
            "input": "all ones; half zeros/half ones", "gradient_seed": "standard normal",
            "limit": "Uniform 0/1 designs: identity. Mixed 0/1 designs: no gradient, explicit error."
        }
        report["checks_passed"] &= (report["saturation_probe"]["all_solid_adjoint_finite"] and worst < 1e-4
                                    and mixed_refused)
        for values, label in ((source, "Input"), (fixed, "Fixed eta=.5"), (actual, "Volume-preserving")):
            axes[0, 0].plot(x.ravel(), values.ravel(), label=label)
        axes[0, 0].set_ylabel("Density")
        axes[0, 1].bar(["Input", "Fixed", "Preserved"], [source.mean(), fixed.mean(), actual.mean()],
                       color=["#8ba7b7", "#b87730", "#245c7e"])
        axes[0, 1].set_ylabel("Mean density")
        np.savetxt(folder / "curves.csv", np.column_stack([x.ravel(), source.ravel(), fixed.ravel(), actual.ravel()]),
                   delimiter=",", header="position,input,fixed,preserved", comments="")
    for axis in axes.flat:
        axis.grid(alpha=.2)
        axis.set_xlabel("Input density" if case_id == "heaviside" else "Normalized position / case")
    axes[0, 0].legend(fontsize=8)
    _finish(figure, case_id, folder)
    return report


def material_figure(case_id, folder):
    case = CASES[case_id]
    scenario, solver = recipe(case_id, showcase=False)
    problem = make_problem(scenario, 1.)
    rho = np.linspace(0, 1, 501)
    cls = INTERPOLATIONS.get(case["spec"]["type"])
    spec = {key: value for key, value in case["spec"].items() if key != "type"}
    columns, errors, original_errors = [rho], [], []
    if case_id == "ordered_simp":
        figure, axes = _figure(1, 3, height=4.4)
        parameters = (1., 3., 5.)
    else:
        figure, axes = _figure(1, 2, height=4.4)
        parameters = (1.1, 2.1, 3.1, 4.1, 5.1) if case_id == "sinh" else (
            (0, 1, 5, 20) if case_id == "ramp" else (None,))
    for number, parameter in enumerate(parameters):
        settings = dict(spec)
        if case_id in {"sinh", "ordered_simp"}:
            settings["penal"] = parameter
        elif case_id == "ramp":
            settings["q"] = parameter
        law = cls(**settings)
        law.setup(problem)
        if case_id == "sinh":
            actual = law.volume_density(rho)
            p = parameter
            expected = 1 - (np.exp(p * (1 - rho)) - np.exp(-p * (1 - rho))) / (np.exp(p) - np.exp(-p))
            axes[0, 0].plot(rho, actual, label=f"p={p:g}")
            axes[0, 1].plot(rho, law.volume_slope(rho), label=f"p={p:g}")
        elif case_id == "hashin_shtrikman":
            actual = law.stiffness(rho, 1., 0.)
            expected = rho / (3 - 2 * rho)
            axes[0, 0].plot(rho, actual, label="Implemented HS")
            axes[0, 0].plot(rho, rho**2, label="SIMP p=2")
            axes[0, 0].plot(rho, rho**3, label="SIMP p=3")
            axes[0, 1].plot(rho, law.slope(rho, 1., 0.), label="HS derivative")
            axes[0, 1].plot(rho, abs(actual - expected), label="Absolute formula error")
        elif case_id == "ramp":
            actual = law.stiffness(rho, 1., 0.)
            # Exact rational evaluations on the same rational input samples.
            expected = np.array([float(Fraction(i, 500) / (1 + parameter * (1 - Fraction(i, 500)))) for i in range(501)])
            axes[0, 0].plot(rho, actual, label=f"q={parameter}")
            axes[0, 1].plot(rho, law.slope(rho, 1., 0.), label=f"q={parameter}")
        else:
            actual = law.stiffness(rho, 1., 1e-9)
            knots, moduli = [0., .4, .6, 1.], [1e-9, .5, .7, 1.]
            expected, original = np.zeros_like(rho), np.zeros_like(rho)
            for i in range(3):
                select = (rho >= knots[i]) & (rho <= knots[i + 1])
                local = (rho[select] - knots[i]) / (knots[i + 1] - knots[i])
                expected[select] = moduli[i] + (moduli[i + 1] - moduli[i]) * local**parameter
                a = (moduli[i + 1] - moduli[i]) / (knots[i + 1]**parameter - knots[i]**parameter)
                original[select] = moduli[i] + a * (rho[select]**parameter - knots[i]**parameter)
            axis = axes[0, number]
            axis.plot(rho, original, ":", color="#b87730", label="Original global power")
            axis.plot(rho, expected, color="#9db6c4", linewidth=3, label="2022 modified")
            axis.plot(rho, actual, "--", color="#245c7e", label="Toporia")
            axis.scatter(knots, moduli, s=14, color="black")
            axis.set_title(f"p={parameter:g}")
            original_errors.append(float(np.max(abs(actual - original))))
        errors.append(float(np.max(abs(actual - expected))))
        columns.extend([actual, expected])
    # Off-knot derivative check, independent of the plot reference evaluation.
    points = np.array([.11, .28, .53, .81])
    h = 1e-6
    if case_id == "sinh":
        finite = (law.volume_density(points + h) - law.volume_density(points - h)) / (2 * h)
        derivative = law.volume_slope(points)
    else:
        emin = 1e-9 if case_id == "ordered_simp" else 0.
        finite = (law.stiffness(points + h, 1., emin) - law.stiffness(points - h, 1., emin)) / (2 * h)
        derivative = law.slope(points, 1., emin)
    derivative_error = float(np.max(abs(finite - derivative)))
    tolerance = 1e-8 if case_id == "ordered_simp" else 1e-12
    report = {"source_curve_parameters": list(parameters), "curve_max_abs_error": max(errors),
              "curve_tolerance": tolerance, "off_knot_derivative_error": derivative_error,
              "checks_passed": max(errors) <= tolerance and derivative_error <= 1e-6}
    if original_errors:
        report.update(original_2017_formula_max_errors=original_errors,
                      original_2017_reproduction_to_fix=True,
                      attribution="Increasing-modulus branch of da Silveira-Palma 2022 modified law; not the original 2017 equation.")
    for axis in axes.flat:
        axis.set_xlabel("Normalized density")
        axis.set_ylabel("Effective cost / slope" if case_id == "sinh" else "Normalized modulus / slope")
        axis.grid(alpha=.2)
        axis.legend(fontsize=7)
    if case_id == "sinh":
        axes[0, 0].plot(rho, rho, color="black", linestyle=":", label="Linear first measure")
        axes[0, 0].legend(fontsize=7)
    np.savetxt(folder / "curves.csv", np.column_stack(columns), delimiter=",")
    _finish(figure, case_id, folder)
    return report


def schedule_figure(case_id, folder, companions=False):
    case = CASES[case_id]
    name = case["spec"]["type"]
    settings = {key: value for key, value in case["spec"].items() if key != "type"}
    schedule = SCHEDULES.get(name)(**settings)
    count = np.arange(451 if name in {"geometric", "settled"} else 201)
    values, expected, changes = [], [], []
    # Deterministic own signal; its role is event testing, never paper digitization.
    change = .08 * np.exp(-count / 27) + .01
    reference_value, began, streak = settings["start"], 0, 0
    for k in count:
        if name == "settled":
            if k and ((k - began >= settings["min_every"] and streak >= settings["settle"]) or k - began >= settings["max_every"]):
                reference_value = min(settings["end"], reference_value * settings["factor"])
                began, streak = k, 0
            expected.append(reference_value)
        elif name == "steps":
            expected.append(min(settings["end"], 1. + .5 * (int(k) // 20)))
        elif name == "geometric":
            expected.append(min(128., 2.**(int(k) // 50)))
        else:
            expected.append(1. if k <= 20 else (3. if k >= 100 else 1. + 2. * (k - 20) / 80))
        values.append(schedule.value(int(k)))
        # observe reports completion k+1 and affects the next iteration.
        if name == "settled":
            schedule.observe(int(k) + 1, float(change[k]))
            streak = streak + 1 if change[k] < settings["change_below"] else 0
        changes.append(float(change[k]))
    values, expected = np.array(values), np.array(expected)
    error = float(np.max(abs(values - expected)))
    figure, axes = _figure(1, 2, height=4.4)
    axes[0, 0].step(count, expected, where="post", color="#b87730", linewidth=3, alpha=.6, label="Independent rule")
    axes[0, 0].plot(count, values, "--", color="#245c7e", label="Implemented")
    axes[0, 0].set_ylabel("Parameter value")
    axes[0, 0].set_xlabel("Completed iterations")
    axes[0, 0].set_title("Rule diagnostic: own controlled signal", fontsize=10)
    axes[0, 0].legend(fontsize=8)
    report = {"clock_rule_error": error, "rule_tolerance": 1e-12, "checks_passed": error < 1e-12,
              "event_signal": "own exponential change signal; not a paper iteration history"}
    if companions:
        from toporia.engine.loop import run_single_with_store
        scenario, solver = recipe(case_id)
        run = Run(scenario, solver).updated(save_every=0).with_output_dir(folder / "companion")
        with contextlib.redirect_stdout(StringIO()):
            store, density = run_single_with_store(run)
        axes[0, 1].plot(np.arange(1, len(store.objectives) + 1), store.objectives, color="#245c7e")
        axes[0, 1].set_ylabel("Pre-update compliance (own MBB companion)")
        axes[0, 1].set_yscale("log")
        axes[0, 1].set_title("Companion: its actual optimization history", fontsize=10)
        parameter_path = case["schedules"][0]["path"]
        parameter_values = store.responses[parameter_path]
        report["companion"] = {"iterations": len(store.objectives), "stop_reason": store.stop_reason,
                               "last_pre_update_compliance": store.objectives[-1],
                               "physical_fraction": float(density.mean()),
                               "parameter_path": parameter_path, "last_parameter": parameter_values[-1],
                               "converged": not store.stop_reason.startswith("iteration limit")}
        np.savetxt(folder / "companion.csv",
                   np.column_stack([np.arange(1, len(store.objectives) + 1), parameter_values,
                                    store.objectives, store.volumes]), delimiter=",",
                   header="iteration,actual_parameter,pre_update_compliance,physical_fraction", comments="")
    else:
        axes[0, 1].plot(count, changes, color="#245c7e")
        axes[0, 1].axhline(.03, linestyle=":", color="#b87730")
        axes[0, 1].set_ylabel("Own change signal (event diagnostic)")
    axes[0, 1].set_xlabel("Iteration index")
    for axis in axes.flat:
        axis.grid(alpha=.2)
    np.savetxt(folder / "schedule.csv", np.column_stack([count, values, expected, changes]), delimiter=",",
               header="completed,implemented,independent,own_change_signal", comments="")
    _finish(figure, case_id, folder)
    return report


def pde_figure(folder, cached_result=None):
    from toporia.engine.loop import initialized_method

    from .research_figures import compare, plot_comparison
    reference = json.loads(PDE_REFERENCE.read_text(encoding="utf-8"))
    if cached_result is None:
        scenario, solver = recipe("pde")
        method = initialized_method(Run(scenario, solver))
        history = []
        try:
            for iteration in range(1, solver.max_iter + 1):
                method.step(iteration)
                history.append([iteration, float(method.get_responses()["objective"]),
                                float(method.get_density().mean()), float(method.get_change())])
                if iteration % 50 == 0:
                    print(f"PDE: {iteration} iterations", flush=True)
                if method.get_change() < solver.tol:
                    break
            fresh = method._model.evaluate(method.x, gradients=False)
            result = {"preset": metadata("pde")[0], "density": method.get_density().tolist(),
                      "history": history, "iterations": iteration,
                      "fresh_final_compliance": float(fresh.objective),
                      "physical_volume_fraction": float(method.get_density().mean()),
                      "stop_reason": "tolerance" if method.get_change() < solver.tol else "max_iter"}
        finally:
            method.close()
    else:
        result = json.loads(Path(cached_result).read_text(encoding="utf-8"))
    comparison = compare(result, reference)
    plot_comparison("PDE density", result, reference, comparison, folder / "figure.png",
                    title="Andreassen et al. Figure 4(b): density PDE filter",
                    settings="150 x 50; radius 6; p=3; OC", reference_label="Unchanged author top82")
    (folder / "solver-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return {"checks_passed": comparison["native_code_match"], "comparison": comparison,
            "iterations": result["iterations"], "fresh_final_compliance": result["fresh_final_compliance"],
            "physical_volume_fraction": result["physical_volume_fraction"],
            "source_sha256": reference["source_sha256"]}


def run_case(case_id, output, *, companions=False, cached_pde=None):
    folder = output / case_id
    folder.mkdir(parents=True, exist_ok=True)
    case = CASES[case_id]
    if case_id == "pde":
        checks = pde_figure(folder, cached_pde)
    elif case_id in {"heaviside", "heaviside_volume"}:
        checks = projection_figure(case_id, folder)
    elif case["kind"] == "interpolation":
        checks = material_figure(case_id, folder)
    elif case["kind"] == "schedule":
        checks = schedule_figure(case_id, folder, companions)
    else:
        checks = field_figure(case_id, folder)
    status = "source_equation_curve_match" if case_id in CURVE_MATCHES and checks["checks_passed"] else (
        "native_code_match" if case_id == "pde" and checks["checks_passed"] else "paper_reproduction_to_fix")
    report = {"schema": 1, "case_id": case_id, "batch": 2, "functions": [case["function"]],
              "preset": metadata(case_id)[0], "source_url": case["source"], "target": case["target"],
              "paper_status": status, "paper_visual_status": "not_assessed",
              "checks": checks, "limitations": case["limits"],
              "parameters": case["spec"], "next_check": NEXT_CHECKS.get(case_id, ""),
              "quarantined_reason": QUARANTINED.get(case_id, ""),
              "generated_at": datetime.now(timezone.utc).isoformat(),
              "reproduce": f"python -m experiments.research_batch2 --case {case_id}"}
    (folder / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    (folder / "description.html").write_text(description_page(metadata(case_id)[0], description(case_id)), encoding="utf-8")
    if status == "paper_reproduction_to_fix" or checks.get("original_2017_reproduction_to_fix"):
        (folder / "TO-FIX.md").write_text(
            f"# {case['label']}: unresolved research comparison\n\nTarget: {case['target']}\n\n"
            f"Known execution issue: {QUARANTINED.get(case_id, 'None observed in the recorded checks.')}\n\n"
            f"Reason: {case['limits']}\n\nNumerical checks: {checks['checks_passed']}.\n"
            "A passing engineering check is not a paper reproduction.\n\n"
            f"Next: {NEXT_CHECKS[case_id]}\n", encoding="utf-8")
    print(f"{case_id}: numerical={checks['checks_passed']}; paper={status}", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["all", *CASES], default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "results/research/batch2/generated")
    parser.add_argument("--companions", action="store_true")
    parser.add_argument("--cached-pde", type=Path, help="Reuse a recorded PDE result for report/plot review; not a fresh solve.")
    parser.add_argument("--strict-paper", action="store_true")
    args = parser.parse_args()
    reports = [run_case(case_id, args.output, companions=args.companions, cached_pde=args.cached_pde)
               for case_id in (CASES if args.case == "all" else [args.case])]
    if not all(report["checks"]["checks_passed"] for report in reports):
        raise SystemExit(1)
    if args.strict_paper and any(report["paper_status"] == "paper_reproduction_to_fix" for report in reports):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
