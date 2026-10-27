"""Fixed-beta recipe stays fixed and improves a physical projected design."""

import numpy as np
import pytest

from experiments.fixed_projection import validate
from toporia.plugins.filters.heaviside import HeavisideFilter
from toporia.plugins.problems import get_run


def test_projection_remains_fixed_beyond_multiple_continuation_intervals():
    specs = get_run("MBB Beam (Fixed Projection)").solver.filter_specs
    part = HeavisideFilter(**{k: v for k, v in specs[1].items() if k != "type"})
    field = np.linspace(0, 1, 41).reshape(1, -1)
    before = part.forward(field)
    for iteration in range(1, 601):
        part.step(iteration)
        assert not part.continuing()
    np.testing.assert_array_equal(part.forward(field), before)


@pytest.mark.parametrize("preset", ["MBB Beam", "Cantilever"])
def test_fixed_projection_optimizes_without_a_beta_schedule(preset):
    result = validate(preset, iterations=100, mesh=0.4)
    assert np.isfinite(result["final_compliance"])
    assert result["final_compliance"] < result["initial_compliance"] * 0.75
    assert result["volume_fraction"] <= result["volume_limit"] + 0.005
    assert result["gray_indicator"] < 0.5
