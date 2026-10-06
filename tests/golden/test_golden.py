"""test_golden.py — characterisation tests.

These do NOT assert that the optimiser is correct.  They assert that it still
does exactly what it did before, so the Phase 1-9 restructure can be verified
mechanically.  A failure means behaviour changed: either fix the regression, or
if the change was intended, run tests/regenerate_baselines.py and commit the
new .npz alongside it.

Tolerance is tight on purpose.  A pure refactor on one machine should reproduce
bit-for-bit; 1e-8 leaves only enough room for library-level float noise.
"""

from pathlib import Path

import numpy as np
import pytest

from tests.golden._harness import run_case
from tests.golden.cases import CASES

BASELINE_DIR = Path(__file__).resolve().parent / "baselines"
ATOL = 1e-8


def _load_baseline(name):
    path = BASELINE_DIR / f"{name}.npz"
    if not path.exists():
        pytest.fail(f"Missing baseline {path.name}. Run: python tests/regenerate_baselines.py {name}")
    return np.load(path)


@pytest.mark.parametrize("name", sorted(CASES))
def test_matches_baseline(name, tmp_path):
    expected = _load_baseline(name)
    actual   = run_case(CASES[name](), tmp_path)

    # Iteration count first: it is the cheapest signal and a change here means
    # the convergence policy moved, which explains any density difference below.
    assert int(actual["iterations"]) == int(expected["iterations"]), (
        f"{name}: iteration count changed "
        f"{int(expected['iterations'])} -> {int(actual['iterations'])}"
    )

    assert actual["density"].shape == expected["density"].shape, (
        f"{name}: density shape changed "
        f"{tuple(expected['density'].shape)} -> {tuple(actual['density'].shape)}"
    )

    obj_e, obj_a = float(expected["objective"]), float(actual["objective"])
    assert obj_a == pytest.approx(obj_e, rel=ATOL), (
        f"{name}: objective changed {obj_e:.10g} -> {obj_a:.10g} "
        f"(relative {abs(obj_a - obj_e) / max(abs(obj_e), 1e-30):.3e})"
    )

    max_diff = float(np.max(np.abs(actual["density"] - expected["density"])))
    assert max_diff < ATOL, (
        f"{name}: density field changed, max |delta| = {max_diff:.3e} "
        f"(mean |delta| = {float(np.mean(np.abs(actual['density'] - expected['density']))):.3e})"
    )


@pytest.mark.parametrize("name", sorted(CASES))
def test_density_is_physically_valid(name, tmp_path):
    """Invariants that must hold for any method, independent of the baseline."""
    density = run_case(CASES[name](), tmp_path)["density"]
    assert np.all(np.isfinite(density)), f"{name}: density contains NaN or inf"
    assert density.min() >= -ATOL, f"{name}: density below 0 ({density.min():.3e})"
    assert density.max() <= 1.0 + ATOL, f"{name}: density above 1 ({density.max():.3e})"
