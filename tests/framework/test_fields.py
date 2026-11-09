"""test_fields.py — several fields per element (Wave 5): multi-material and fibre angles.

A representation may describe more than the density.  The model hands each extra field to
the part that reads it (the DMO material law, the orthotropic physics); the gradient with
respect to the density, the material weights and the angles is exact; the volume budget
counts the materials' masses; and a mismatched setup is refused before the run.
"""

from dataclasses import replace

import numpy as np
import pytest

from toporia_core.engine.loop import initialized_method
from toporia_library.problems import get_run


def _model(method, representation, interpolation=None, problem="MBB Beam", objective=None):
    run = get_run(problem).updated(method=method, max_iter=3, tol=0.0, m=0.5)
    solver = replace(run.solver, representation=representation, filter_specs=[{"type": "density"}],
                     **({"interpolation": interpolation} if interpolation else {}))
    scenario = replace(run.scenario, objective=objective) if objective else run.scenario
    method = initialized_method(replace(run, solver=solver, scenario=scenario))
    return method._model, method


def _check_gradient(model, z, which, rtol=1e-4):
    evaluation = model.evaluate(z)
    for name, gradient in (("objective", evaluation.objective_gradient), ("volume", evaluation.volume_gradient)):
        for index in which:
            step = 1e-4                      # central differences: O(h²) error, above solver round-off
            up, down = z.copy(), z.copy()
            up[index] += step
            down[index] -= step
            low, high = model.evaluate(down, gradients=False), model.evaluate(up, gradients=False)
            fd = (getattr(high, name) - getattr(low, name)) / (2 * step)
            # Absolute tolerance from the largest entry: a tiny entry is limited by solver round-off.
            scale = float(np.max(np.abs(gradient)))
            assert gradient[index] == pytest.approx(fd, rel=rtol, abs=1e-6 * scale), (name, index)


def test_multi_material_gradients_are_exact():
    model, _ = _model("q4+mma", {"type": "multi_material", "materials": 3}, {"type": "dmo"})
    rng = np.random.default_rng(7)
    z = model.representation.initial()
    z[0] = rng.uniform(0.3, 0.9, z[0].shape)
    z[1:] = rng.uniform(0.2, 0.8, z[1:].shape)
    ny, nx = z.shape[1:]
    _check_gradient(model, z, [(0, 3, 5), (1, ny // 2, nx // 3), (2, 2, nx - 3), (3, ny - 2, 4)])


def test_fibre_angle_gradients_are_exact():
    model, _ = _model("q4_orthotropic+mma", {"type": "fibre_angle", "start_angle": 20.0})
    rng = np.random.default_rng(8)
    z = model.representation.initial()
    z[0] = rng.uniform(0.3, 0.9, z[0].shape)
    z[1] = rng.uniform(-1.0, 1.0, z[1].shape)
    ny, nx = z.shape[1:]
    _check_gradient(model, z, [(0, 2, 3), (1, 1, 1), (1, ny // 2, nx // 2), (1, ny - 2, nx - 2)])


def test_multi_material_in_3d_and_with_heat():
    model, _ = _model("h8+mma", {"type": "multi_material"}, {"type": "dmo"}, problem="Cantilever 3D")
    z = model.representation.initial()
    _check_gradient(model, z, [(1, 0, 1, 2), (2, 0, 2, 5)])
    heat, _ = _model("q4_heat+mma", {"type": "multi_material"}, {"type": "dmo"}, problem="Heat Sink")
    z = heat.representation.initial()
    _check_gradient(heat, z, [(1, 3, 4), (2, 6, 6)])


def test_the_budget_counts_the_mass_of_the_chosen_material():
    model, _ = _model("q4+mma", {"type": "multi_material"}, {"type": "dmo", "mass_1": 1.0, "mass_2": 0.3})
    z = model.representation.initial()
    z[0], z[1], z[2] = 1.0, 1.0, 0.0                  # all material 1
    heavy = model.evaluate(z, gradients=False).volume
    z[1], z[2] = 0.0, 1.0                              # all material 2
    light = model.evaluate(z, gradients=False).volume
    assert light == pytest.approx(0.3 * heavy)


def test_fibres_along_the_load_are_stiffer():
    model, _ = _model("q4_orthotropic+mma", {"type": "fibre_angle"}, problem="Cantilever")
    z = model.representation.initial()
    z[0] = 1.0
    along = model.evaluate(z, gradients=False).objective           # fibres along the beam (x)
    z[1] = np.pi / 2
    across = model.evaluate(z, gradients=False).objective
    assert along < across


def test_short_runs_lower_the_compliance():
    for method, representation, interpolation in (("q4+mma", {"type": "multi_material"}, {"type": "dmo"}),
                                                  ("q4_orthotropic+mma", {"type": "fibre_angle"}, None)):
        _, opt = _model(method, representation, interpolation)
        values = []
        for i in range(1, 7):
            opt.step(i)
            values.append(opt.get_responses()["objective"])
        assert values[-1] < values[0], method


@pytest.mark.parametrize("method, representation, interpolation, objective, message", [
    ("q4+mma", {"type": "multi_material"}, None, None, "need a reader"),
    ("q4+mma", {"type": "fibre_angle"}, None, None, "need a reader"),
    ("q4+mma", {"type": "multi_material"}, {"type": "dmo"}, {"type": "peak_stress"}, "several fields"),
])
def test_a_mismatched_setup_is_refused(method, representation, interpolation, objective, message):
    with pytest.raises(ValueError, match=message):
        _model(method, representation, interpolation, objective=objective)
