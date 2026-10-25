"""test_local_stress.py — local stress constraints by the augmented Lagrangian method.

The response owns one multiplier per element; the updater moves them between
outer iterations.  Tested here: the penalty's gradient against finite
differences with multipliers that are not zero, the multiplier update exactly as
specified, and the L-bracket benchmark on a coarse mesh — every element within
(about) its limit and a rounded re-entrant corner, which the compliance design
does not have.
"""

import numpy as np
import pytest

from toporia.engine.loop import initialized_method
from toporia.framework.params import resolve_params
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.models.q4 import Q4Model
from toporia.plugins.problems import get_run
from toporia.plugins.responses.local_stress import LocalStress


def _response(problem="MBB Beam", m=0.3, **values):
    run = get_run(problem).updated(m=m)
    mesh = make_problem(run.scenario, m)
    engine = Q4Model.physics()
    engine.initialize(mesh, resolve_params("q4", Q4Model.params, {}))
    response = LocalStress()
    response.setup(engine, mesh, resolve_params("local_stress", LocalStress.params, values))
    return response, engine, mesh


def test_gradient_matches_finite_differences_with_nonzero_multipliers():
    response, engine, mesh = _response(limit=1e-3, epsilon=0.1, penalty=3.0)
    rng = np.random.default_rng(0)
    density = rng.uniform(0.3, 0.9, mesh.shape)
    response.evaluate(engine.solve(density))
    response.update_multipliers(growth=1.0)            # multipliers are now non-zero
    assert np.max(response.multipliers) > 0
    result = response.evaluate(engine.solve(density))
    for index in [(1, 2), (3, 5), (mesh.shape[0] - 2, mesh.shape[1] - 3)]:
        step = 1e-6
        up, down = density.copy(), density.copy()
        up[index] += step
        down[index] -= step
        fd = (response.evaluate(engine.solve(up), gradient=False).value
              - response.evaluate(engine.solve(down), gradient=False).value) / (2 * step)
        assert result.gradient[index] == pytest.approx(fd, rel=1e-4, abs=1e-9)


def test_multipliers_follow_the_specified_update():
    """λ ← λ + μ h with h = max(g, −λ/μ), μ ← min(α μ, μ_max); λ never goes negative."""
    response, engine, mesh = _response(limit=1.0, penalty=2.0, penalty_max=5.0, epsilon=0.0)
    density = np.full(mesh.shape, 0.7)
    state = engine.solve(density)
    stress = engine.element_stress(state, 0)
    vm = np.sqrt(np.einsum("...i,ij,...j->...", stress, np.array([[1, -.5, 0], [-.5, 1, 0], [0, 0, 3.]]), stress))
    g = density ** 0.5 * vm / 1.0 - 1.0
    response.evaluate(state)
    response.update_multipliers(growth=2.0)
    assert np.allclose(response.multipliers[0], np.maximum(2.0 * g, 0.0), atol=1e-6)
    assert response.mu == 4.0
    first = response.multipliers.copy()
    response.evaluate(state)
    response.update_multipliers(growth=2.0)
    h = np.maximum(g, -first[0] / 4.0)
    assert np.allclose(response.multipliers[0], first[0] + 4.0 * h, atol=1e-6)
    assert response.mu == 5.0                         # capped
    assert response.multipliers.min() >= 0.0


def _corner_density(density):
    """Mean density of the material elements within three elements of the re-entrant corner."""
    n = density.shape[0]
    cut = round(0.4 * n)                              # the arm width, in elements; row 0 is the bottom; the corner node is at row and column cut
    rows, cols = np.mgrid[:n, :n]
    near = (abs(rows - cut) <= 3) & (abs(cols - cut) <= 3)
    material = (cols < cut) | (rows < cut)
    return float(density[near & material].mean())


def test_l_bracket_meets_the_limit_and_rounds_the_corner(capsys):
    reference = get_run("L-bracket")
    oc = initialized_method(reference)
    for i in range(1, 101):
        oc.step(i)

    run = get_run("L-bracket (local stress)")
    method = initialized_method(run)
    for i in range(1, run.solver.max_iter + 1):
        method.step(i)
    responses = method.get_responses()
    limit = run.scenario.constraints[0]["limit"]

    # The stress of the compliance design, measured with the same constraint.
    oc_stress = method._model.evaluate(oc.x, gradients=False).reported["max_stress"]
    ratio = responses["max_stress"] / limit
    print(f"\ncompliance design: volume {oc.get_density().mean():.3f}, max stress/limit {oc_stress / limit:.2f}, "
          f"corner density {_corner_density(oc.get_density()):.2f}")
    print(f"local stress design: volume {method.get_density().mean():.3f}, max stress/limit {ratio:.3f}, "
          f"corner density {_corner_density(method.get_density()):.2f}")

    assert ratio <= 1.05
    assert responses["constraint_0_local_stress_exact"] == pytest.approx(ratio - 1.0)
    assert oc_stress / limit > 1.2                        # the compliance design violates the limit
    assert _corner_density(method.get_density()) < _corner_density(oc.get_density()) - 0.05   # corner relieved


def test_local_stress_is_refused_with_an_updater_that_would_misread_its_penalty():
    import pytest
    from toporia.engine.loop import initialized_method
    from toporia.framework.problem.run import apply_param
    from toporia.plugins.problems import get_run
    run = apply_param(apply_param(get_run("L-bracket (local stress)"), "method", "q4+nlopt_mma"), "method_params", {})
    with pytest.raises(ValueError, match="only works with the updater 'augmented_lagrangian'"):
        initialized_method(run)
