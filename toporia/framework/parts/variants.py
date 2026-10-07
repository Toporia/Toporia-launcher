# framework/parts/variants.py — one design, evaluated in several versions at once.
#
# Some formulations evaluate every design more than once and optimise the
# combination.  The robust formulation of Wang, Lazarov & Sigmund (2011)
# projects the design with three thresholds — eroded (η = 0.75), intermediate
# (0.5), dilated (0.25) — and minimises the worst of the three compliances;
# its result keeps a minimum length scale and tolerates manufacturing error.
# Load uncertainty is the same idea with load cases, and a tolerance study
# with perturbed geometry.  All are one setting in the solver:
#
#     solver.variants = {"path": "filters[1].eta", "values": [0.75, 0.5, 0.25],
#                        "combine": "worst", "nominal": 1}
#
# `path` is any parameter path (framework/problem/run.py); each value gives
# one variant: the same model built with that value.  VariantModel evaluates
# them all at every design and joins them into one Evaluation, so updaters,
# responses and filters do not change at all:
#
#     objective    combine="worst":  a smooth maximum (Kreisselmeier–Steinhauser),
#                      f = s/ρ · log Σ exp(ρ f_i / s),   max ≤ f ≤ max + s·log(n)/ρ,
#                  with ρ the `sharpness` and s the largest objective of the
#                  last iteration: held fixed within an iteration, so the
#                  gradient (each variant's weighted by softmax(ρ f_i / s)) is
#                  exact, and renewed between iterations, so f stays within
#                  log(n)/ρ (2 % for three variants) of the true worst case,
#                  which is recorded as well ("worst_case")
#                  combine="mean":   the average, for an expected value
#     constraints  combined the same way, variant by variant (already normalised,
#                  so s = 1)
#     volume, the design shown, the start design and the bounds: the
#                  `nominal` variant's (the intermediate design, the "blueprint")
#
# Each variant costs its own physics solve, and the run's solve count says so.
#
# Differences from Wang et al. 2011: the worst case is a smooth maximum rather
# than a bound formulation with one constraint per variant (which needs an
# updater that enforces several constraints), and the volume budget applies to
# the intermediate design rather than to the dilated one with an updated
# limit.  Both are common simplifications in the papers that followed.

import numpy as np

from toporia.framework.parts.model import ConstraintValue, Evaluation, Model

#: How the variants' values are joined.
COMBINE = {"worst": "Worst case (smooth maximum)", "mean": "Mean (expected value)"}


def variant_label(path, value):
    """How one variant is named in the history: "filters[1].eta=0.75"."""
    return f"{path}={value:g}"


class VariantModel(Model):
    """Several models of the same design, joined into one: the worst case or the mean."""

    def __init__(self, models, path, values, combine="worst", nominal=None, sharpness=50.0):
        if len(models) < 2:
            raise ValueError("variants need at least two values")
        if combine not in COMBINE:
            raise ValueError(f"combine must be one of {sorted(COMBINE)}, got {combine!r}")
        self.models = list(models)
        self.path, self.values = path, list(values)
        self.combine = combine
        self.nominal = len(models) // 2 if nominal is None else int(nominal)
        if not 0 <= self.nominal < len(models):
            raise ValueError(f"nominal must index one of the {len(models)} variants, got {nominal}")
        self.sharpness = float(sharpness)
        self._scale = None
        self._last_objectives = np.ones(len(models))

        main = self.models[self.nominal]
        self.name, self.label = main.name, main.label
        self.capabilities = main.capabilities
        self.problem = main.problem
        self.volume_limit = main.volume_limit
        shapes = {np.shape(model.initial_design()) for model in self.models}
        if len(shapes) != 1:
            raise ValueError(f"the variants of {path!r} have different design shapes {sorted(shapes)}; "
                             f"vary something that leaves the design variables alone")

    def initialize(self, problem, solver, settings):
        raise TypeError("a VariantModel is built from models that are already initialised")

    # ── The nominal variant's ─────────────────────────────────────────────────

    def initial_design(self):
        return self.models[self.nominal].initial_design()

    def bounds(self):
        return self.models[self.nominal].bounds()

    def physical(self, x):
        return self.models[self.nominal].physical(x)

    def volume_of(self, x):
        return self.models[self.nominal].volume_of(x)

    def geometry(self, x):
        return self.models[self.nominal].geometry(x)

    # ── All of them ───────────────────────────────────────────────────────────

    def evaluate(self, x, gradients=True):
        evaluations = [model.evaluate(x, gradients=gradients) for model in self.models]
        nominal = evaluations[self.nominal]
        objectives = np.array([e.objective for e in evaluations], dtype=float)
        if self._scale is None:
            self._scale = max(float(np.max(np.abs(objectives))), 1e-12)
        objective, weights = self._join(objectives, self._scale)
        gradient = (sum(w * e.objective_gradient for w, e in zip(weights, evaluations, strict=True))
                    if gradients else None)

        constraints = []
        for j, first in enumerate(nominal.constraints):
            values = np.array([e.constraints[j].value for e in evaluations])
            value, w = self._join(values, 1.0)
            grad = sum(wi * e.constraints[j].gradient for wi, e in zip(w, evaluations, strict=True)) if gradients else None
            exacts = [e.constraints[j].exact for e in evaluations]
            exact = None if any(v is None for v in exacts) else (
                max(exacts) if self.combine == "worst" else float(np.mean(exacts)))
            constraints.append(ConstraintValue(first.name, value, grad, exact=exact))

        self._last_objectives = objectives
        reported = dict(nominal.reported)
        if self.combine == "worst":
            reported["worst_case"] = float(np.max(objectives))
        for value, e in zip(self.values, evaluations, strict=True):
            reported[f"objective[{variant_label(self.path, value)}]"] = e.objective
        return Evaluation(objective=objective, objective_gradient=gradient,
                          volume=nominal.volume, volume_gradient=nominal.volume_gradient,
                          constraints=tuple(constraints), reported=reported)

    def _join(self, values, scale):
        """The combined value and each variant's weight in its gradient."""
        if self.combine == "mean":
            return float(np.mean(values)), np.full(len(values), 1.0 / len(values))
        a = self.sharpness * values / scale
        top = float(np.max(a))
        exp = np.exp(a - top)                       # shifted, so nothing overflows
        weights = exp / exp.sum()
        return float(scale / self.sharpness * (top + np.log(exp.sum()))), weights

    def advance(self, completed):
        # Renew the smooth maximum's scale between iterations (see the top of this file).
        self._scale = max(float(np.max(np.abs(self._last_objectives))), 1e-12)
        for model in self.models:
            model.advance(completed)

    def continuing(self):
        return any(model.continuing() for model in self.models)

    def set_parameter(self, path, value):
        for model in self.models:
            model.set_parameter(path, value)
