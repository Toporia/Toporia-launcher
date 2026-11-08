# framework/optimisers/flat_view.py — the problem as an optimisation library sees it.
#
# Optimisers from the literature and from libraries (MMA, SciPy, NLopt, IPOPT,
# pyMOTO) all want the same thing: a vector, its bounds, and callbacks
#
#     f(x)   the objective              df(x)   its gradient, shape (n,)
#     g(x)   the constraints, shape (m,)  dg(x)   their Jacobian, shape (m, n)
#
# FlatProblem presents any Model that way, so an adapter never repeats the
# bookkeeping between a design and that vector:
#
#   * the design is flattened (column-major by default) and only the FREE
#     variables are kept: an element whose lower and upper bounds coincide
#     (inside a hole, on a solid ring) cannot move, and many optimisers divide
#     by the bound range;
#   * the volume budget becomes the first constraint, g_0 = V / V_limit − 1,
#     followed by the scenario's constraints in order;
#   * constraints follow Toporia's convention, g ≤ 0 is satisfied; g_geq and
#     dg_geq give SciPy's g ≥ 0 so no adapter has to get the sign right itself;
#   * the objective can be rescaled to start at a chosen value, because MMA-type
#     subproblems assume objective and constraints of similar size;
#   * the last design is cached, so asking for f, g, df and dg at the same
#     point costs one physics solve.  Values come with their gradients by
#     default, since most optimisers ask for both; a gradient-free optimiser
#     (or a line search) sets values_with_gradients=False and then never pays
#     for a sensitivity analysis it does not use.
#
#     design (nely, nelx) ──reduce──> x (n,)  ──f, df, g, dg──> optimiser
#     design (nely, nelx) <──expand── x (n,)  <───────────────── new x

import numpy as np

#: Name of the first constraint, the volume budget every method enforces.
VOLUME_BUDGET = "volume budget"


class FlatProblem:
    """A Model as a flat vector problem: x0, bounds, f, df, g, dg.

    model              : a framework.parts.model.Model, already initialised
    scale_objective_to : rescale the objective so its first evaluated value has
                         this magnitude (10 is the usual choice for MMA); None
                         leaves it unscaled.  The factor is fixed once, so the
                         problem does not change between iterations.
    order              : "F" (column-major, top88's element numbering) or "C"
    values_with_gradients : compute the gradients whenever a value is computed,
                         so a later df or dg at the same point needs no new solve
    """

    def __init__(self, model, scale_objective_to=None, order="F", values_with_gradients=True):
        self.model = model
        self._order = order
        self._values_with_gradients = values_with_gradients
        lower, upper = model.bounds()
        self.shape = np.shape(lower)
        lower = np.asarray(lower, dtype=float).reshape(-1, order=order)
        upper = np.asarray(upper, dtype=float).reshape(-1, order=order)
        self.free = upper > lower
        self._fixed_values = lower.copy()   # a fixed variable sits at its (equal) bounds
        self.lower, self.upper = lower[self.free], upper[self.free]
        self.n = int(np.count_nonzero(self.free))
        self.n_fixed = int(self.free.size - self.n)
        self.x0 = self.reduce(model.initial_design())

        self._scale_target = scale_objective_to
        self.objective_scale = 1.0 if scale_objective_to is None else None
        self._cached = None          # (x bytes, Evaluation)
        self.evaluations = 0         # model.evaluate calls made through this view
        self.gradient_evaluations = 0

    # ── Between the design and the vector ─────────────────────────────────────

    def reduce(self, design):
        """The free variables of a design, as a vector."""
        return np.asarray(design, dtype=float).reshape(-1, order=self._order)[self.free]

    def expand(self, x):
        """The full design for a vector of free variables; fixed ones at their bounds."""
        full = self._fixed_values.copy()
        full[self.free] = x
        return full.reshape(self.shape, order=self._order)

    # ── Evaluation, cached ────────────────────────────────────────────────────

    def remember(self, design, evaluation):
        """Hand over an evaluation that was already computed for this design.

        Updaters receive one from the engine every iteration; remembering it
        means asking for f, g or their gradients there costs no extra solve.
        """
        self._store(self.reduce(design), evaluation)

    def evaluation(self, x, gradients=True):
        """The model's Evaluation at x (free variables), from the cache when possible."""
        gradients = gradients or self._values_with_gradients
        x = np.asarray(x, dtype=float)
        cached = self._cached
        if cached is not None and cached[0] == x.tobytes():
            if not gradients or cached[1].objective_gradient is not None:
                return cached[1]
        evaluation = self.model.evaluate(self.expand(x), gradients=gradients)
        self.evaluations += 1
        self.gradient_evaluations += int(gradients)
        self._store(x, evaluation)
        return evaluation

    def forget(self):
        """Drop the cached evaluation: the problem itself changed (a schedule moved a parameter)."""
        self._cached = None

    def cached(self, x):
        """The cached Evaluation if it is for exactly x (free variables), else None."""
        if self._cached is not None and self._cached[0] == np.asarray(x, dtype=float).tobytes():
            return self._cached[1]
        return None

    def _store(self, x, evaluation):
        self._cached = (np.asarray(x, dtype=float).tobytes(), evaluation)
        if self.objective_scale is None:
            self.objective_scale = self._scale_target / max(abs(evaluation.objective), 1e-12)

    # ── The callbacks ─────────────────────────────────────────────────────────

    def f(self, x):
        """Objective (scaled)."""
        evaluation = self.evaluation(x, gradients=False)
        return self.objective_scale * evaluation.objective

    def df(self, x):
        """Gradient of the objective (scaled), shape (n,)."""
        evaluation = self.evaluation(x)
        return self.objective_scale * self.reduce(evaluation.objective_gradient)

    def g(self, x):
        """Constraints, g ≤ 0 satisfied: the volume budget, then the scenario's constraints."""
        evaluation = self.evaluation(x, gradients=False)
        volume = float(evaluation.volume / self.model.volume_limit) - 1.0
        return np.array([volume, *(c.value for c in evaluation.constraints)])

    def dg(self, x):
        """Jacobian of g, shape (m, n)."""
        evaluation = self.evaluation(x)
        rows = [self.reduce(evaluation.volume_gradient / self.model.volume_limit)]
        rows += [self.reduce(c.gradient) for c in evaluation.constraints]
        return np.vstack(rows)

    def g_geq(self, x):
        """Constraints in the g ≥ 0 convention (SciPy's 'ineq')."""
        return -self.g(x)

    def dg_geq(self, x):
        """Jacobian of g_geq."""
        return -self.dg(x)

    # ── Description ───────────────────────────────────────────────────────────

    @property
    def m(self):
        """Number of constraints, the volume budget included."""
        return len(self.constraint_names)

    @property
    def constraint_names(self):
        """Names of the constraints in g's order.

        Read from the scenario when the model has one, so describing the view
        costs no solve; otherwise from an evaluation (the start design's, once).
        """
        if self._cached is not None:
            return [VOLUME_BUDGET, *(c.name for c in self._cached[1].constraints)]
        scenario = getattr(getattr(self.model, "problem", None), "scenario", None)
        if scenario is not None:
            return [VOLUME_BUDGET, *(spec["type"] for spec in scenario.constraints)]
        evaluation = self.evaluation(self.x0, gradients=False)
        return [VOLUME_BUDGET, *(c.name for c in evaluation.constraints)]

    def describe(self):
        """One line on what the optimiser sees, for the console."""
        scale = ("objective unscaled" if self._scale_target is None
                 else f"objective scaled to start at {self._scale_target:g}")
        return (f"{self.n} free variables ({self.n_fixed} fixed, left out), "
                f"{self.m} constraint(s) g <= 0: {', '.join(self.constraint_names)}; {scale}")
