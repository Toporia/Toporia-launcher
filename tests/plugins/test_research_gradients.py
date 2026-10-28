"""The final-design gradient evidence (experiments/research_gradients.py) is complete and current."""

import json

import pytest

from experiments.research_gradients import OUTPUT, TOLERANCE, cases, probe

REPORT = json.loads(OUTPUT.read_text(encoding="utf-8"))
RECORDS = {(r["batch"], r["case"]): r for r in REPORT["cases"]}


def test_every_saved_showcase_design_is_probed():
    assert {(batch, name) for batch, name, _, _ in cases()} <= RECORDS.keys()


def test_every_record_passes_or_says_why_it_cannot_be_checked():
    for record in RECORDS.values():
        assert record["status"] in {"passed", "no_interior", "not_composed"}, record
        if record["status"] == "passed":
            assert max(record["best"].values()) < TOLERANCE
            assert record["interior"] > 0
        else:
            assert record["reason"]


@pytest.mark.parametrize("name", ["mma", "oc_multi"])
def test_a_fresh_probe_reproduces_the_saved_errors(name):
    case = next(c for c in cases() if c[:2] == ("batch3", name))
    fresh, saved = probe(*case), RECORDS[("batch3", name)]
    assert fresh["status"] == saved["status"] == "passed"
    for key, value in saved["best"].items():
        assert fresh["best"][key] == pytest.approx(value, rel=1e-3, abs=1e-12)
