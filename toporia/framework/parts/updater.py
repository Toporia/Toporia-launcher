# framework/parts/updater.py — HOW the design moves: an Evaluation in, the next design out.
#
# An Updater knows nothing about the physics that produced the numbers, so
# every updater works with every model.  Two helpers for optimisers written
# for vectors live in framework/optimisers: the flat view (any updater can
# use it) and the external loop (for a library that runs its own loop).

from abc import ABC, abstractmethod


class Updater(ABC):
    """How the design moves: an Evaluation in, the next design out.

    An updater that works on a flat vector, as almost every optimiser from a
    library does, sets `flat_view = True` and builds its view with
    self.flat_problem(model) (framework/optimisers/flat_view.py): free variables only, the volume
    budget as the first constraint, both sign conventions, caching.
    """

    #: Registry key (plugins.updaters.UPDATERS).  An empty name means "abstract".
    name = ""
    label = ""
    order = 100
    #: Tunable parameters (framework.params.Param); they become method parameters.
    params = ()
    #: Objective types the update rule is valid for; None means any.
    objectives = None
    #: How many scenario constraints it can enforce besides the volume budget;
    #: None means any number.  The conservative default is none.
    max_constraints = 0
    #: True when it works on framework.optimisers.flat_view.FlatProblem rather than on the design array.
    flat_view = False
    #: True when it runs its own loop in the background (framework/optimisers/external_loop.py).
    own_loop = False
    #: The flat view's objective rescaling (see FlatProblem); None leaves it unscaled.
    flat_objective_scale = None
    #: True when the update rule only makes sense on one density per element
    #: (OC, BESO): it is then refused with any other design representation
    #: (framework/parts/representation.py).
    needs_element_densities = False
    #: Parameters a schedule may change during a run (framework/parts/schedule.py).
    schedulable = ()

    def flat_problem(self, model):
        """This updater's flat view of `model`, with the declared objective scaling."""
        from toporia.framework.optimisers.flat_view import FlatProblem
        self.flat = FlatProblem(model, scale_objective_to=self.flat_objective_scale)
        return self.flat

    @abstractmethod
    def initialize(self, model, settings):
        """Prepare for a run.  `settings` holds this updater's own Param values."""

    @abstractmethod
    def update(self, x, evaluation, completed):
        """Return the next design.  `completed` counts finished iterations from 0."""

    def is_converged(self, change):
        """Optional stricter stopping criterion; see OptimizationMethod.is_converged."""
        return False

    def convergence_reason(self):
        """Why is_converged() said so, in words; None for the generic message."""
        return None

    def cached_evaluation(self, design):
        """An Evaluation of `design` the updater already has, to spare the engine a solve; or None."""
        return None

    def report(self):
        """The optimiser's own verdict (success, message, its counts) for run.json; or None."""
        return None

    def close(self):
        """Release anything still running (a background optimiser thread).  Called once, at the end."""
