"""cases.py — the golden-baseline case definitions.

One place that describes every scenario the regression suite pins down.
Both test_golden.py and regenerate_baselines.py import CASES from here, so a
case can never drift between the generator and the assertion.

Each case is deliberately small (coarse mesh, few iterations) so the whole
suite runs in seconds.  `tol=0.0` disables the early-exit convergence check,
which makes the iteration count fixed and therefore assertable.
"""

from toporia.framework import LoadCase, Run
from toporia.plugins.problems import get_run


def _base(problem_name: str, **overrides) -> Run:
    """Load a problem preset and apply the shared 'make it small and fast' settings."""
    return get_run(problem_name).updated(
        m=overrides.pop("m", 0.4),
        max_iter=overrides.pop("max_iter", 12),
        tol=0.0,          # never converge early -> iteration count is deterministic
        save_every=0,     # no intermediate PNGs; keeps the suite fast
        **overrides,
    )


# name -> zero-argument builder returning a fully configured Run.
# Chosen to cover every code path the framework has:
#   OC update, MMA update, level-set update, the FEA solver, the filter chain,
#   passive/void masks, and the multi-load-case weighted compliance sum.
CASES = {
    # Core density method (OC) on the canonical benchmark.
    "mbb_oc":        lambda: _base("MBB Beam", method="density"),

    # Same physics, different update rule — pins the MMA path.
    "mbb_mma":       lambda: _base("MBB Beam", method="density_mma"),

    # Different boundary conditions (fixed edge + point load).
    "cantilever_oc": lambda: _base("Cantilever", method="density"),

    # Holes, passive rings and void regions — the mask-enforcement path.
    "drone_arm_oc":  lambda: _base("Drone Arm", method="density", m=0.3, max_iter=10),

    # RBF level-set: a completely different design-variable representation.
    "mbb_levelset":  lambda: _base("MBB Beam", method="levelset", max_iter=10),

    # A multi-stage filter chain — density -> heaviside -> symmetry.
    # Covers FilterChain.forward/backward and the per-iteration step() hook.
    "mbb_filters":   lambda: _base(
        "MBB Beam",
        method="density",
        filter_specs=[
            {"type": "density"},
            {"type": "heaviside", "beta": 1.0, "beta_interval": 4},
            {"type": "symmetry", "axis": "left_right"},
        ],
    ),

    # 3-D: the quick cantilever on H8 bricks, with the 3-D density filter.
    "cantilever_3d_oc": lambda: _base("Cantilever 3D", method="h8+oc"),

    # Two weighted load cases — pins the weighted compliance sum in solve_fea.
    "cantilever_2lc": lambda: _base(
        "Cantilever",
        method="density",
        load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=0.5),
                    LoadCase(Fmag=1.0, Fa=0.0,   weight=0.5)],
    ),
}
