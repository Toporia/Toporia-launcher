"""test_variants.py — one design evaluated in several versions (framework/parts/variants.py).

The robust formulation (eroded / intermediate / dilated projections) is the
main use; the wrapper itself is generic over any parameter path.
"""

import json

import numpy as np
import pytest

from toporia.engine.loop import initialized_method, run_single_with_store
from toporia.engine.pipeline import pipeline_stages
from toporia.framework.parts.variants import VariantModel
from toporia.plugins.problems import get_run

FILTERS = [{"type": "density"}, {"type": "heaviside", "beta": 4.0, "beta_max": 4.0}]
ROBUST = {"path": "filters[1].eta", "values": [0.75, 0.5, 0.25]}


def _run(**values):
    return get_run("MBB Beam").updated(**{"m": 0.3, "max_iter": 6, "tol": 0.0, "save_every": 0,
                                          "method": "q4+mma", "filter_specs": FILTERS, **values})


def test_each_variant_is_solved_and_the_worst_is_optimised():
    method = initialized_method(_run(variants=ROBUST))
    assert isinstance(method._model, VariantModel)
    method.step(1)
    responses = method.get_responses()
    assert responses["solves"] == 3
    eroded, nominal, dilated = (responses[f"objective[filters[1].eta={v:g}]"] for v in (0.75, 0.5, 0.25))
    assert eroded > nominal > dilated                      # less material is less stiff
    assert responses["worst_case"] == eroded
    # The smooth maximum is an upper bound, within log(3)/50 of the start scale.
    assert eroded <= responses["objective"] <= eroded * (1 + np.log(3) / 50) * 1.5


def test_the_smooth_maximum_has_an_exact_gradient():
    method = initialized_method(_run(variants=ROBUST))
    model = method._model
    rng = np.random.default_rng(0)
    x = np.clip(model.initial_design() + rng.uniform(-0.1, 0.1, model.initial_design().shape), 0.01, 0.99)
    gradient = model.evaluate(x).objective_gradient
    for index in np.argsort(-np.abs(gradient.ravel()))[:4]:
        step = np.zeros_like(x)
        step.flat[index] = 1e-6
        fd = (model.evaluate(x + step, gradients=False).objective
              - model.evaluate(x - step, gradients=False).objective) / 2e-6
        assert fd == pytest.approx(gradient.flat[index], rel=1e-3)


def test_the_mean_is_the_average():
    method = initialized_method(_run(variants={**ROBUST, "combine": "mean"}))
    method.step(1)
    responses = method.get_responses()
    each = [responses[f"objective[filters[1].eta={v:g}]"] for v in (0.75, 0.5, 0.25)]
    assert responses["objective"] == pytest.approx(np.mean(each))


def test_a_scenario_path_gives_each_variant_its_own_loads():
    """Uncertain load direction: the same wrapper, varying a load case."""
    run = _run(variants={"path": "load_cases[0].Fa", "values": [260.0, 270.0, 280.0]}, filter_specs=[{"type": "density"}])
    method = initialized_method(run)
    method.step(1)
    responses = method.get_responses()
    values = [responses[f"objective[load_cases[0].Fa={v:g}]"] for v in (260, 270, 280)]
    assert len(set(values)) == 3


def test_the_run_records_and_shows_the_variants(tmp_path):
    run = _run(variants=ROBUST, max_iter=3).with_output_dir(tmp_path)
    assert dict(pipeline_stages(run))["Variants"].startswith("worst case of filters[1].eta = 0.75, 0.5, 0.25")
    store, _ = run_single_with_store(run)
    assert store.responses["solves"][-1] == 9
    record = json.loads((tmp_path / "run.json").read_text())
    assert record["solver"]["definition"]["variants"] == ROBUST


@pytest.mark.parametrize("variants, method, reason", [
    ({"path": "m", "values": [0.3, 0.4]}, "q4+mma", "share the mesh"),
    ({"path": "method.move", "values": [0.1, 0.2]}, "q4+mma", "belongs to the updater"),
    ({"path": "filters[1].eta", "values": [0.5]}, "q4+mma", "at least two"),
    ({"path": "filters[7].eta", "values": [0.4, 0.6]}, "q4+mma", "not a parameter"),
    (ROBUST, "levelset", "evaluates its own designs"),
])
def test_variants_that_cannot_work_are_refused_before_the_run(variants, method, reason):
    with pytest.raises(ValueError, match=reason):
        initialized_method(_run(variants=variants, method=method))


def test_a_path_cannot_be_both_varied_and_scheduled():
    run = _run(variants=ROBUST, schedules=[{"path": "filters[1].eta", "type": "linear", "start": 0.4, "end": 0.5}])
    with pytest.raises(ValueError, match="both varied and scheduled"):
        initialized_method(run)
