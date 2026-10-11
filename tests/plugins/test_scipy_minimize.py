"""test_scipy_minimize.py — the SciPy trust-constr updater in plugins/updaters/scipy_minimize.py.

It must meet the full conformance check, including the MBB benchmark.  (Gradient-free COBYQA and
COBYLA were tried and cannot: about +50 % over OC on the benchmark, so they are not registered.)
"""

import numpy as np
from scipy.optimize import OptimizeResult

from toporia.checks import conformance
from toporia.plugins.updaters import UPDATERS
from toporia.plugins.updaters.scipy_minimize import ScipyTrustConstr, _design, _moves_only


def test_trust_constr_conforms_including_the_benchmark():
    conformance("updater:scipy_trust_constr").assert_ok()


def test_trust_constr_is_registered_for_the_gui_pickers():
    assert UPDATERS.get("scipy_trust_constr").label
    assert ScipyTrustConstr.max_constraints is None
    assert {p.name for p in ScipyTrustConstr.params} >= {"trust_constr_maxiter", "trust_constr_hessian"}


def test_every_callback_form_yields_the_design():
    x = np.array([0.1, 0.2])
    assert np.array_equal(_design(x), x)                                  # (xk)
    assert np.array_equal(_design(x, OptimizeResult(x=x)), x)             # trust-constr: (xk, state)
    assert np.array_equal(_design(OptimizeResult(x=x)), x)                # an OptimizeResult alone


def test_repeated_designs_are_not_reported():
    seen = []
    report = _moves_only(seen.append, np.zeros(2))
    report(np.zeros(2))                  # still the start design
    report(np.array([0.1, 0.0]))
    report(np.array([0.1, 0.0]))         # a rejected step repeats it
    report(np.array([0.2, 0.0]))
    assert len(seen) == 2
