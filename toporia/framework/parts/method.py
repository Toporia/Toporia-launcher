# framework/parts/method.py — the interface every optimisation algorithm must satisfy.
#
# This module deliberately contains no mathematics and imports nothing from
# toporia.plugins.  It is the whole agreement between the engine (which drives
# the loop, records results and compares runs) and a method (which knows how to
# turn design variables into a density field).
#
# Anything a method needs that is NOT in this file is that method's own business.
#
# Data flow, in full:
#
#     engine                                            method
#     ------                                            ------
#     initialize(problem, solver)  ───────────────────>  build internal state,
#                                                        reading its own values
#                                                        from solver.method_params
#     step(iteration)              ───────────────────>  advance one iteration
#     get_density()                <───────────────────  (nely, nelx) array in [0, 1]
#     get_responses()              <───────────────────  {"objective": float, ...}
#     get_change()                 <───────────────────  design-change metric
#
# The engine owns the loop counter and the stopping decision.  A method reports
# what happened; it does not decide when to quit.

from abc import ABC, abstractmethod
from dataclasses import dataclass

from toporia.framework.params import resolve_params

# Every responses dict must contain this key.  It is the quantity being
# minimised, and the only response the comparison engine currently plots.
OBJECTIVE = "objective"


@dataclass(frozen=True)
class Capabilities:
    """What a method can do, so the engine and GUI can adapt instead of warn.

    variable_kind   : what the design variables are, e.g. "density" or "level_set"
    accepts_filters : whether solver.filter_specs is honoured
    accepts_interpolation : whether solver.interpolation (the material law) is honoured
    accepts_representation : whether solver.representation (what the design variables are) is honoured
    dims            : spatial dimensions supported
    objectives      : response types the method can minimise (scenario.objective)
    constraints     : response types it can enforce in scenario.constraints; the
                      volume budget (scenario.volfrac) is always enforced as well
    max_constraints : how many scenario.constraints at once; None means any number
    needs_constraint: objectives that are only meaningful with a further constraint
                      (minimising volume alone gives an empty design), so a method
                      that can enforce none does not offer them
    """
    variable_kind: str = "density"
    accepts_filters: bool = False
    accepts_interpolation: bool = False
    accepts_representation: bool = False
    dims: tuple = (2,)
    objectives: tuple = ("compliance",)
    constraints: tuple = ()
    max_constraints: int | None = 0
    needs_constraint: tuple = ()

    def problems_with(self, scenario):
        """Return why the method cannot solve `scenario` — an empty list when it can."""
        reasons = []
        objective = scenario.objective.get("type", "compliance")
        if objective not in self.objectives:
            reasons.append(f"it cannot minimise {objective!r} (it can minimise: {', '.join(self.objectives)})")
        kinds = [spec.get("type") for spec in scenario.constraints]
        unsupported = sorted({kind for kind in kinds if kind not in self.constraints}, key=str)
        if unsupported:
            enforceable = ", ".join(self.constraints) or "none besides the volume budget"
            reasons.append(f"it cannot enforce {unsupported} constraints (it can enforce: {enforceable})")
        elif self.max_constraints is not None and len(kinds) > self.max_constraints:
            reasons.append(f"it enforces at most {self.max_constraints} constraint(s) besides the "
                           f"volume budget, but the scenario has {len(kinds)}")
        return reasons


class OptimizationMethod(ABC):
    """Interface contract that every optimisation algorithm must satisfy.

    ABC (Abstract Base Class) enforces that any subclass MUST implement every
    method marked @abstractmethod.  If it doesn't, Python refuses to instantiate
    it.

    Most gradient-based methods are not written against this class directly
    but assembled from a Model and an Updater (framework/parts/composition.py).

    A method also describes itself through class attributes.  The registry
    (toporia.plugins.methods.METHODS) finds every subclass with a `name`, the
    GUI builds its panel from `params`, and `capabilities` tells both what the
    method supports.
    """

    #: Registry key used in config.method.  An empty name means "abstract".
    name = ""
    #: Human-readable name for menus.
    label = ""
    #: Other names make_method accepts, e.g. for configs written before a rename.
    aliases = ()
    #: Menu position; lower comes first.
    order = 100
    #: Tunable parameters, as framework.params.Param declarations.
    params = ()
    capabilities = Capabilities()
    #: Method parameters a schedule may change during a run (framework/parts/schedule.py).
    schedulable = ()

    @classmethod
    def resolve_params(cls, solver):
        """Return this method's parameter values: solver.method_params over the defaults.

        Raises ValueError for a key the method does not declare, so a misspelt
        or stale parameter stops the run before it starts.
        """
        return resolve_params(f"method {cls.name!r}", cls.params, solver.method_params)

    @abstractmethod
    def initialize(self, problem, solver):
        """Prepare internal state.  Called once, before the first step.

        `problem` is a framework.problem.mesh.BaseProblem built from the scenario:
        geometry, node masks, per-element density bounds, and problem.scenario
        for the material, volume target and load cases.  It carries no
        degree-of-freedom numbering — a method brings its own conventions.

        `solver` is the framework.problem.solver.Solver: this method's parameters (read them
        with resolve_params) and, for methods that accept them, the filter
        pipeline in solver.filter_specs.
        """

    @abstractmethod
    def step(self, iteration):
        """Advance the design by one iteration.

        `iteration` is supplied by the engine and counts from 1.  Methods that
        need it (filter continuation schedules, warm-up phases) should use this
        value rather than keeping a private counter that could drift out of sync
        with the engine's.
        """

    @abstractmethod
    def get_density(self):
        """Return the current physical density as an (nely, nelx) array in [0, 1].

        This is the universal currency of the platform: it is the only output
        every method must produce, and the only thing the comparison engine
        needs in order to compare two designs from different algorithms.
        """

    @abstractmethod
    def get_responses(self):
        """Return the current scalar responses as a dict.

        Must contain the key `OBJECTIVE`.  Any additional entries (volume,
        constraint values, a continuation parameter such as Heaviside beta) are
        recorded in the run history and become available to the comparison
        engine.  Keys should be stable across iterations.
        """

    @abstractmethod
    def get_change(self):
        """Return a scalar measure of how much the design moved this iteration.

        The engine compares this against solver.tol to decide when to stop, so
        it must shrink as the design settles.  Return float("inf") before the
        first step.
        """

    def set_parameter(self, path, value):
        """Change the value at a parameter path during a run, as a schedule does before each iteration.

        A whole method changes its own declared `schedulable` parameters
        ("method.<name>") by attribute; a composed method routes any path to
        the part that owns it.
        """
        from toporia.framework.parts.schedule import change_parameter
        prefix, _, name = path.rpartition(".")
        if prefix != "method":
            raise ValueError(f"{self.label or type(self).__name__} cannot change {path!r} during a run")
        change_parameter(self, name, value)

    def continuing(self):
        """True while a continuation of the method's own is still moving; the engine then does not stop."""
        return False

    def geometry(self):
        """Explicit outlines of the current design (closed polygons in mm), for export; None for a density design."""
        return None

    def is_converged(self):
        """Optional method-specific stopping criterion.

        The engine's own rule — `get_change() < solver.tol` — applies to every
        method and is what makes cross-method benchmarks comparable.  Override
        this only for a criterion that genuinely cannot be expressed as a design
        change (the RBF level-set's joint volume-and-compliance stability test is
        the motivating example).

        When a method stops a run this way the engine records it as the stop
        reason, so a benchmark never silently compares runs halted by different
        rules.
        """
        return False

    def convergence_reason(self):
        """Why is_converged() returned True, in words; None for a generic message."""
        return None

    def report(self):
        """The optimiser's own account of how it ended (success, message, counts), or None.

        Recorded in run.json next to the engine's stop reason.  Libraries that
        run their own loop report one; Toporia's own updaters do not need to.
        """
        return None

    def close(self):
        """Release anything still running.  The engine calls this once, however the run ends."""
