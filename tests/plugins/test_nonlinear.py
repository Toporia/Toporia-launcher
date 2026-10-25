"""test_nonlinear.py — large-displacement elasticity (q4_nonlinear) and its end-compliance response.

What is pinned: the element tangent against differences of the element force; agreement with the
linear Q4 model for a small load; a real difference, and a converging Newton, for a large one;
the adjoint sensitivity against finite differences at a load where the structure really moves;
the clear error when Newton cannot follow; and the preset.
"""

import numpy as np
import pytest

from toporia.engine.loop import initialized_method
from toporia.framework.problem.mesh import RectangularProblem
from toporia.plugins.models.q4 import Q4Model
from toporia.plugins.models.q4_nonlinear import Q4NonlinearModel
from toporia.plugins.physics.q4_nonlinear import NonlinearConvergenceError, NonlinearElement
from toporia.plugins.problems import get_run

SETTINGS = {"penal": 3.0, "steps": 10, "newton_tol": 1e-11, "max_newton": 40, "linear_below": 0.1, "linear_above": 0.2}


def _model(cls, load, m=0.4, objective=None, **settings):
    """The cantilever preset's geometry at tip load `load`, on a coarse mesh, with a density filter."""
    run = get_run("Nonlinear Cantilever").updated(m=m, filter_specs=[{"type": "density"}], **{"load_cases[0].Fmag": load})
    run = run.updated(objective=objective or {"type": "end_compliance" if cls is Q4NonlinearModel else "compliance"})
    model = cls()
    model.initialize(RectangularProblem(run.scenario, run.solver.m), run.solver, {**SETTINGS, **settings})
    return model


def _design(model, seed=3):
    """A smooth-ish random design between 0.2 and 0.9: material everywhere, some soft and some stiff."""
    rng = np.random.default_rng(seed)
    return np.clip(model.initial_design() + rng.uniform(-0.2, 0.5, model.initial_design().shape), 0.2, 0.9)


def test_element_tangent_is_the_derivative_of_the_element_force():
    element = NonlinearElement(0.3, 1.0, 2.0)
    rng = np.random.default_rng(0)
    Ue = rng.uniform(-0.3, 0.3, (3, 8))
    _, K = element.force_and_tangent(Ue)
    h = 1e-6
    for j in range(8):
        plus, minus = Ue.copy(), Ue.copy()
        plus[:, j] += h
        minus[:, j] -= h
        column = (element.force_and_tangent(plus, False)[0] - element.force_and_tangent(minus, False)[0]) / (2 * h)
        assert np.allclose(K[:, :, j], column, atol=1e-8)
    assert np.allclose(K, K.transpose(0, 2, 1))                       # hyperelastic: symmetric


def test_small_load_matches_the_linear_model():
    linear, nonlinear = _model(Q4Model, 1e-4), _model(Q4NonlinearModel, 1e-4)
    x = _design(linear)
    c_lin = linear.evaluate(x, gradients=False).objective
    c_non = nonlinear.evaluate(x, gradients=False).objective
    assert abs(c_non - c_lin) / c_lin < 1e-3
    g_lin, g_non = linear.evaluate(x).objective_gradient, nonlinear.evaluate(x).objective_gradient
    assert np.linalg.norm(g_non - g_lin) / np.linalg.norm(g_lin) < 1e-3


def test_large_load_differs_and_newton_converges():
    linear, nonlinear = _model(Q4Model, 0.05), _model(Q4NonlinearModel, 0.05)
    x = _design(linear)
    c_lin = linear.evaluate(x, gradients=False).objective
    c_non = nonlinear.evaluate(x, gradients=False).objective
    assert abs(c_non - c_lin) / c_lin > 0.02
    # The engine solved it: every load step needed Newton iterations, none hit the cap.
    state = nonlinear.engine.solve(nonlinear.physical(x))
    assert all(0 < n < SETTINGS["max_newton"] for n in state.increments[0])


def test_end_compliance_sensitivity_matches_finite_differences():
    model = _model(Q4NonlinearModel, 0.05)
    x = _design(model)
    gradient = model.evaluate(x).objective_gradient
    order = np.argsort(-np.abs(gradient), axis=None)[:6]
    worst = 0.0
    for flat in order:
        index = np.unravel_index(flat, x.shape)
        plus, minus = x.copy(), x.copy()
        plus[index] += 1e-5
        minus[index] -= 1e-5
        fd = (model.evaluate(plus, gradients=False).objective - model.evaluate(minus, gradients=False).objective) / 2e-5
        worst = max(worst, abs(fd - gradient[index]) / abs(fd))
    print(f"largest relative error of the end-compliance sensitivity: {worst:.2e}")
    assert worst < 1e-5


def test_sensitivity_is_exact_inside_the_density_blend_band():
    # Densities between linear_below and linear_above exercise the s'(rho) term of the adjoint.
    model = _model(Q4NonlinearModel, 0.05, linear_below=0.3, linear_above=0.5)
    x = _design(model)
    gradient = model.evaluate(x).objective_gradient
    index = np.unravel_index(np.argmax(np.abs(gradient)), x.shape)
    plus, minus = x.copy(), x.copy()
    plus[index] += 1e-5
    minus[index] -= 1e-5
    fd = (model.evaluate(plus, gradients=False).objective - model.evaluate(minus, gradients=False).objective) / 2e-5
    assert gradient[index] == pytest.approx(fd, rel=1e-5)


def test_newton_failure_is_a_clear_error():
    model = _model(Q4NonlinearModel, 5.0, steps=1, max_newton=3)
    with pytest.raises(NonlinearConvergenceError, match="did not converge beyond 0.0% of the load"):
        model.evaluate(_design(model), gradients=False)


def test_preset_runs_and_nonlinear_design_differs_from_the_linear_one():
    iterations = 25
    designs = {}
    for method, objective in (("q4_nonlinear+mma", "end_compliance"), ("q4+mma", "compliance")):
        run = get_run("Nonlinear Cantilever").updated(method=method, max_iter=iterations, save_every=0, m=0.4,
                                                    objective={"type": objective})
        method_object = initialized_method(run)
        for iteration in range(1, iterations + 1):
            method_object.step(iteration)
        designs[method] = method_object.get_density()
        assert np.all(np.isfinite(designs[method]))

    # Both designs judged by both laws, at the preset's load.
    linear, nonlinear = _model(Q4Model, 0.03, m=0.4), _model(Q4NonlinearModel, 0.03, m=0.4, steps=10)

    def compliances(density):
        """(linear, non-linear) compliance of a physical density."""
        return (linear.objective.evaluate(linear.engine.solve(density), gradient=False).value,
                nonlinear.objective.evaluate(nonlinear.engine.solve(density), gradient=False).value)

    table = {name: compliances(density) for name, density in designs.items()}
    print("compliance (linear law, non-linear law) of the design from:", table)
    # The design made with the non-linear law is the better one under that law, the two laws give
    # different compliances for it, and the two designs are not the same picture.
    non_design, lin_design = table["q4_nonlinear+mma"], table["q4+mma"]
    assert non_design[1] <= lin_design[1] * 1.001
    assert abs(non_design[1] - non_design[0]) / non_design[0] > 0.005
    difference = np.abs(designs["q4_nonlinear+mma"] - designs["q4+mma"]).mean()
    print(f"mean density difference between the two designs: {difference:.3f}")
    assert difference > 0.02
