# framework/problem/solver.py — HOW a scenario is solved.
#
# A Solver names the method and holds everything that belongs to solving rather
# than to the physical problem: the method's own parameters, the filter
# pipeline, the mesh resolution and the stopping rule.
#
# Two runs that share a scenario and differ only in their solver are a
# benchmark — the comparison Toporia exists to make.  Solvers round-trip
# through JSON (framework/problem/files.py) just like scenarios.

from dataclasses import dataclass, field

from toporia.framework.params import Param


@dataclass(frozen=True)
class Solver:
    """The method, its parameters, its filters, the discretisation and the stopping rule."""

    # ── Method ────────────────────────────────────────────────────────────────
    # Either "<model>+<updater>" — any model with any updater, e.g. "q4+oc",
    # "q4+mma" or "pymoto_elastic+pymoto_gcmma" — or a whole method such as
    # "levelset".  See toporia.plugins.methods.  The names used before the
    # split ("density", "density_mma", "pymoto", ...) are still accepted.
    method: str = "q4+oc"

    # The parameters of the method's parts — the model's and the updater's
    # together — keyed by Param name.  Anything left out uses the declared
    # default; an unknown key is an error.  Example: {"move": 0.1, "mma_tol": 1e-5}
    method_params: dict = field(default_factory=dict)

    # The material law for models whose physics interpolates stiffness from
    # density, {"type": <interpolation name>, <param>: <value>}; see
    # framework/parts/interpolation.py.  Other models (pyMOTO's, the level
    # set) bring their own and ignore it.
    interpolation: dict = field(default_factory=lambda: {"type": "simp"})

    # What the design variables are, {"type": <representation name>, <param>: <value>}:
    # one density per element (the default), or e.g. the bars of moving
    # morphable components; see framework/parts/representation.py.  It also
    # sets the start design.  Models that keep their own variables (pyMOTO's,
    # the level set) ignore it.
    representation: dict = field(default_factory=lambda: {"type": "element_density"})

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
# and filter parameters are declared on their own classes in toporia.plugins.
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
