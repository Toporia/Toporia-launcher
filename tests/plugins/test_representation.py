"""test_representation.py — what the design variables are, as a part of its own.

The element densities were the only possible design; they are now one
representation among others, chosen in the solver like the filters and the
material law.  These tests pin that the default is unchanged, that moving
morphable components optimise through the same model and updaters, that a
pairing which cannot work is refused before the run, and that the choice is
visible and recorded.
"""

import json

import numpy as np
import pytest

from toporia.engine.loop import initialized_method, run_single
from toporia.engine.pipeline import pipeline_notes, pipeline_parts, pipeline_stages, solver_problems
from toporia.framework.problem.mesh import RectangularProblem
from toporia.framework.problem.run import apply_param, read_param
from toporia.plugins.catalog import parameter_paths
from toporia.plugins.methods import method_class
from toporia.plugins.problems import get_run
from toporia.plugins.representations import REPRESENTATIONS
from toporia.plugins.representations.element_density import ElementDensity
from toporia.plugins.representations.mmc import PER_BAR, MovingMorphableComponents

MMC = {"type": "mmc"}


def _run(**values):
    return get_run("MBB Beam").updated(**{"m": 0.5, "max_iter": 8, "tol": 0.0, "save_every": 0, **values})


def _problem(name="MBB Beam", m=0.5):
    run = get_run(name)
    return RectangularProblem(run.scenario, m)


def test_both_are_registered_and_element_densities_are_the_default():
    assert REPRESENTATIONS.names() == ["element_density", "mmc"]
    assert _run().solver.representation == {"type": "element_density"}


def test_element_densities_start_uniform_or_full_within_the_bounds():
    problem = _problem("Drone Arm")
    uniform, full = ElementDensity(), ElementDensity(start="full")
    uniform.setup(problem)
    full.setup(problem)
    lower, upper = uniform.bounds()
    for start in (uniform.initial(), full.initial()):
        assert np.all(lower <= start) and np.all(start <= upper)
    free = upper > lower
    assert np.allclose(uniform.initial()[free], problem.scenario.volfrac)
    assert np.allclose(full.initial()[free], 1.0)


def test_a_full_start_reaches_the_model():
    method = initialized_method(_run(method="q4+mma", representation={"type": "element_density", "start": "full"}))
    assert method.get_density().mean() > 0.95


def test_mmc_starts_as_crossing_bars_and_its_gradient_is_exact():
    problem = _problem()
    bars = MovingMorphableComponents(n_x=3, n_y=2)
    bars.setup(problem)
    z = bars.initial()
    assert z.size == 3 * 2 * 2 * PER_BAR and bars.n_bars == 12
    field = bars.density(z)
    assert field.shape == (problem.nely, problem.nelx) and 0.0 <= field.min() and field.max() <= 1.0

    z = np.clip(z + np.random.default_rng(1).uniform(-0.03, 0.03, z.size), 0.0, 1.0)
    weights = np.random.default_rng(2).normal(size=field.shape)
    gradient = bars.backward(z, weights)
    for i in np.argsort(-np.abs(gradient))[:10]:
        step = np.zeros_like(z)
        step[i] = 1e-6
        fd = (np.sum(weights * bars.density(z + step)) - np.sum(weights * bars.density(z - step))) / 2e-6
        assert fd == pytest.approx(gradient[i], rel=1e-4, abs=1e-8 * np.abs(gradient).max())


def test_bars_are_optimised_by_mma_through_the_same_model():
    run = _run(method="q4+mma", representation=MMC, method_params={"move": 0.02}, max_iter=40)
    method = initialized_method(run)
    objectives = []
    for iteration in range(1, run.solver.max_iter + 1):
        method.step(iteration)
        objectives.append(method.get_responses()["objective"])
    assert objectives[-1] < 0.5 * objectives[0]
    assert method.get_density().mean() == pytest.approx(run.scenario.volfrac, abs=0.02)
    assert method.describe_view().startswith(f"{16 * PER_BAR} free variables")


def test_holes_stay_void_whatever_the_bars_do():
    run = get_run("Drone Arm").updated(m=0.3, max_iter=2, tol=0.0, save_every=0, method="q4+mma",
                                       representation=MMC, method_params={"move": 0.02})
    method = initialized_method(run)
    method.step(1)
    problem = method.problem
    pinned = problem.upper_bound <= problem.lower_bound
    assert np.array_equal(method.get_density()[pinned], problem.lower_bound[pinned])


@pytest.mark.parametrize("updater", ["oc", "beso", "simpl"])
def test_an_updater_that_moves_element_densities_is_refused_with_bars(updater):
    run = _run(method=f"q4+{updater}", representation=MMC)
    with pytest.raises(ValueError, match="moves one density per element"):
        initialized_method(run)
    assert solver_problems(method_class(f"q4+{updater}"), run.solver)
    assert any("would be refused" in note for note in pipeline_notes(run.solver.method, run.solver))
    assert not solver_problems(method_class("q4+mma"), run.solver)


def test_models_with_their_own_variables_ignore_it():
    run = _run(method="levelset", representation=MMC)
    assert not method_class("levelset").capabilities.accepts_representation
    assert not solver_problems(method_class("levelset"), run.solver)
    assert "representation" not in [kind for kind, _ in pipeline_parts(run)]


def test_the_choice_is_shown_advised_and_recorded(tmp_path):
    run = _run(method="q4+mma", representation={"type": "mmc", "n_x": 2}, max_iter=2,
               method_params={"move": 0.02}).with_output_dir(tmp_path)
    assert dict(pipeline_stages(run))["Design"] == "Moving morphable components, projected onto the elements"
    assert dict(pipeline_stages(_run()))["Design"] == "Element densities"
    assert any("move limit" in note for note in pipeline_notes(run.solver.method, run.solver))
    run_single(run)
    record = json.loads((tmp_path / "run.json").read_text())
    assert record["solver"]["definition"]["representation"] == {"type": "mmc", "n_x": 2}
    assert [p["name"] for p in record["parts"] if p["kind"] == "representation"] == ["mmc"]


def test_its_parameters_are_paths_a_sweep_can_vary():
    run = apply_param(_run(representation=MMC), "representation.n_x", 3)
    assert read_param(run, "representation.n_x") == 3
    paths = [path for _, path in parameter_paths("q4+mma", representation=MMC)]
    assert {"representation.n_x", "representation.edge_width"} <= set(paths)
    assert not any(path.startswith("representation.")
                   for _, path in parameter_paths("levelset", representation=MMC))


def test_a_misspelt_parameter_fails_before_computing():
    with pytest.raises(ValueError, match="nx"):
        initialized_method(_run(method="q4+mma", representation={"type": "mmc", "nx": 3}))
