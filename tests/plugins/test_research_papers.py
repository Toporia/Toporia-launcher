"""The published-number comparisons (experiments/research_papers.py) are complete, consistent and honest."""

import contextlib
import json

import numpy as np
import pytest

from experiments.research_papers import CASES, EVIDENCE, MATCH
from toporia.engine.loop import initialized_method
from toporia.framework import Run
from toporia.plugins.problems import get_run, problem_description

REPORTS = {name: json.loads((EVIDENCE / name / "report.json").read_text(encoding="utf-8"))
           for name in CASES if (EVIDENCE / name / "report.json").exists()}


#: Cases not run to completion yet: 2500 steps on 30 000 elements, about four hours for the three (To do.md).
PENDING = {"top99neo_t1", "top99neo_t2", "top99neo_t3"}


def test_every_case_has_published_evidence():
    assert CASES.keys() - PENDING <= REPORTS.keys() <= CASES.keys()


@pytest.mark.parametrize("name", sorted(REPORTS))
def test_the_verdict_follows_the_recorded_difference(name):
    report = REPORTS[name]
    reference = CASES[name][2]
    measured = report["compliance"] / REPORTS[reference]["compliance"] if reference else report["compliance"]
    assert report["measured"] == pytest.approx(measured, rel=1e-12)
    assert report["relative_difference"] == pytest.approx(measured / CASES[name][1] - 1, rel=1e-12)
    matched = abs(report["relative_difference"]) <= MATCH
    assert report["paper_status"] == ("published_value_match" if matched else "paper_reproduction_to_fix")
    assert report["volume_fraction"] == pytest.approx(0.5, abs=1e-3)


def test_the_saved_reference_field_has_the_recorded_compliance():
    scenario, solver = CASES["machining_reference"][0]()
    with contextlib.redirect_stdout(None):
        method = initialized_method(Run(scenario, solver))
    try:
        model = method._model
        density = np.load(EVIDENCE / "machining_reference" / "final-density.npy")
        state = model.engine.solve(density)
        assert model.objective.evaluate(state, gradient=False).value == pytest.approx(
            REPORTS["machining_reference"]["compliance"], rel=1e-6)
    finally:
        method.close()


@pytest.mark.parametrize("preset", ["Paper: top99neo Table 2 T3 (MBB)", "Paper: Machining Fig. 6b (cantilever)"])
def test_the_presets_carry_their_paper_description(preset):
    run = get_run(preset)
    description = problem_description(preset)
    assert description is not None and description.source_url.startswith("https://arxiv.org/")
    assert run.solver.max_iter >= 400
