# core/solver.py — HOW a scenario is solved.
#
# A Solver names the method and holds everything that belongs to solving rather
# than to the physical problem: the method's own parameters, the filter
# pipeline, the mesh resolution and the stopping rule.
#
# Two runs that share a scenario and differ only in their solver are a
# benchmark — the comparison Toporia exists to make.  Solvers round-trip
# through JSON (core/serialize.py) just like scenarios.

from dataclasses import dataclass, field

from .params import Param


@dataclass(frozen=True)
class Solver:
    """The method, its parameters, its filters, the discretisation and the stopping rule."""

    # ── Method ────────────────────────────────────────────────────────────────
    # Name of a registered method (see toporia.library.methods.METHODS), e.g.
    # "density", "density_mma", "levelset" or "pymoto".
    method: str = "density"

    # The method's own parameters, keyed by Param name.  Anything left out uses
    # the default declared on the method class; an unknown key is an error.
    # Example: {"penal": 3.5, "move": 0.1}
    method_params: dict = field(default_factory=dict)

    # Filters applied in order, each {"type": <filter name>, <param>: <value>}.
    # Only honoured by methods whose capabilities say accepts_filters=True.
    # Empty list means raw optimiser output with no filtering.
    filter_specs: list = field(default_factory=lambda: [{"type": "density"}])

    # ── Discretisation ────────────────────────────────────────────────────────
    # Elements per millimetre: the mesh is round(Lx*m) x round(Ly*m) elements.
    # It lives here rather than in the Scenario because resolution is a choice
    # about solving the problem, and a mesh study is a comparison of solvers.
    m: float = 1.0

    # ── Stopping rule ─────────────────────────────────────────────────────────
    # Applied by the engine to every method alike, which is what keeps a
    # cross-method comparison fair.
    max_iter: int = 100     # hard iteration limit
    tol: float = 0.01       # stop when the design change a method reports is below tol


# Param declarations for the solver fields the GUI and sweeps expose.  Method
# and filter parameters are declared on their own classes in toporia.library.
SOLVER_PARAMS = (
    Param("m", 1.0, "Mesh res m",
          "Elements per millimetre. Higher values give finer designs but slower FEA.",
          min=0.1, max=5.0, step=0.1, decimals=2, units="el/mm"),
    Param("max_iter", 100, "Max iters",
          "Maximum number of optimisation iterations before stopping.", min=1, max=2000),
    Param("tol", 0.01, "Tolerance",
          "Stop when the design change reported by the method falls below this value.",
          min=0.0, max=1.0, step=0.005, decimals=4),
)
