# framework/parts/composition.py — a method assembled from a model and an updater.
#
# A gradient-based topology-optimisation method is two independent choices:
#
#     Model    WHAT is optimised: turns a design into an objective, a material
#              volume, the scenario's constraints, and the gradients of all of
#              them.  The physics, the filters and the sensitivity analysis
#              live here.
#     Updater  HOW the design moves: turns those numbers into the next design
#              (optimality criteria, MMA, GCMMA, ...).
#
# ComposedMethod is the glue.  It implements core.contract.OptimizationMethod,
# so the engine cannot tell a composed method from a hand-written one, and it
# fixes the one ordering that matters:
#
#     evaluation = model.evaluate(x)             objective, volume, constraints, gradients
#     model.advance(completed)                   continuation (e.g. Heaviside beta)
#     x_new = updater.update(x, evaluation, …)   may call the model's cheap parts
#     density = model.physical(x_new)            what is reported and drawn
#
# The two halves meet only through Evaluation and the Model methods below, so
# any model works with any updater — within what each can do: a composed
# method can minimise what its model can compute AND its updater can handle.
#
# A model is itself usually assembled from parts — filters, a physics engine
# (core/physics.py) and responses — see library/models/assembled.py.

from dataclasses import replace

import numpy as np

from toporia.framework.parts.method import OBJECTIVE, Capabilities, OptimizationMethod


def _subset(settings, params):
    return {p.name: settings[p.name] for p in params}


def _combine(model_capabilities, updater):
    """A composed method can do what its model computes AND its updater handles."""
    objectives = model_capabilities.objectives
    if updater.objectives is not None:
        objectives = tuple(o for o in objectives if o in updater.objectives)
    limits = [n for n in (model_capabilities.max_constraints, updater.max_constraints) if n is not None]
    max_constraints = min(limits) if limits else None
    constraints = model_capabilities.constraints if max_constraints != 0 else ()
    if not constraints:
        objectives = tuple(o for o in objectives if o not in model_capabilities.needs_constraint)
    return replace(model_capabilities, objectives=objectives, constraints=constraints,
                   max_constraints=max_constraints)


class ComposedMethod(OptimizationMethod):
    """An OptimizationMethod made of a Model and an Updater.

    Pairings are not declared one by one: compose(model, updater) builds the
    method for any pair, named "<model>+<updater>" (e.g. "q4+mma"), and
    library.methods.method_class turns such a name into it.  A subclass may
    still be written by hand:

        class MyPairing(ComposedMethod):
            name, label = "mine", "My pairing"
            model = Q4Model
            updater = OCUpdater

    The method's parameters are the model's followed by the updater's.  Its
    capabilities are the model's, narrowed to what the updater can handle.
    """

    model = None
    updater = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.model is None or cls.updater is None:
            return
        combined = tuple(cls.model.params) + tuple(cls.updater.params)
        names = [p.name for p in combined]
        clashes = sorted({n for n in names if names.count(n) > 1})
        if clashes:
            raise TypeError(
                f"{cls.__name__}: {cls.model.__name__} and {cls.updater.__name__} both declare "
                f"{clashes}; parameter names must be unique within a method"
            )
        cls.params = combined
        cls.capabilities = _combine(cls.model.capabilities, cls.updater)

    def initialize(self, problem, solver):
        if type(self).model is None or type(self).updater is None:
            raise TypeError(f"{type(self).__name__} must set both `model` and `updater`")
        settings = self.resolve_params(solver)
        self.problem = problem
        self._model = type(self).model()
        self._updater = type(self).updater()
        self._model.initialize(problem, solver, _subset(settings, self._model.params))
        self._count_solves(self._model)
        self._updater.initialize(self._model, _subset(settings, self._updater.params))

        self.x = self._model.initial_design()
        self.density = self._model.physical(self.x)
        self.objective = np.inf
        self.change = np.inf
        self._evaluation = None

    def step(self, iteration):
        completed = iteration - 1   # continuation schedules count finished iterations
        evaluation = self._updater.cached_evaluation(self.x) or self._model.evaluate(self.x)
        self._model.advance(completed)
        x_new = self._updater.update(self.x, evaluation, completed)

        self.change = float(np.max(np.abs(x_new - self.x)))
        self.x = x_new
        self.density = self._model.physical(x_new)
        self.objective = evaluation.objective
        self._evaluation = evaluation

    def _count_solves(self, model):
        """Count every model evaluation — the engine's, and any an updater makes itself.

        Updaters differ in how many physics solves an iteration costs (GCMMA
        re-evaluates trial designs), so iterations alone do not compare them
        fairly.  The count is Toporia's own, whatever the updater reports.
        """
        self.solves = 0
        evaluate = model.evaluate

        def counted(x, gradients=True):
            self.solves += 1
            return evaluate(x, gradients=gradients)

        model.evaluate = counted

    def describe_view(self):
        """What the updater's optimiser sees, when it works on a flat view; else None."""
        flat = getattr(self._updater, "flat", None)
        return flat.describe() if flat is not None else None

    def is_converged(self):
        return self._updater.is_converged(self.change)

    def convergence_reason(self):
        return self._updater.convergence_reason()

    def report(self):
        return self._updater.report()

    def close(self):
        self._updater.close()

    def get_density(self):   return self.density
    def get_change(self):    return self.change

    def get_responses(self):
        responses = {OBJECTIVE: self.objective, "volume": float(self.density.mean()),
                     "solves": self.solves}
        if self._evaluation is not None:
            responses.update(self._evaluation.reported)
            for i, constraint in enumerate(self._evaluation.constraints):
                responses[f"constraint_{i}_{constraint.name}"] = constraint.value
                if constraint.exact is not None:
                    responses[f"constraint_{i}_{constraint.name}_exact"] = constraint.exact
        return responses


#: Separates the model from the updater in a composed method's name: "q4+mma".
SEPARATOR = "+"

_composed = {}


def compose(model_cls, updater_cls):
    """Return the method made of this model and this updater, built once per pair."""
    key = (model_cls, updater_cls)
    if key not in _composed:
        _composed[key] = type(
            f"{model_cls.__name__}_{updater_cls.__name__}", (ComposedMethod,),
            {"name": f"{model_cls.name}{SEPARATOR}{updater_cls.name}",
             "label": f"{model_cls.label} · {updater_cls.label}",
             "model": model_cls, "updater": updater_cls},
        )
    return _composed[key]


def explain(model_cls, updater_cls):
    """Plain-language reasons why this pairing offers less than one of its parts could.

    Empty when nothing is lost.  The GUI shows these next to the selectors, so a
    missing objective, constraint or filter list is explained, not just absent.
    """
    notes = []
    model = model_cls.capabilities
    combined = _combine(model, updater_cls)
    lost = [name for name in model.objectives if name not in combined.objectives]
    rule = updater_cls.objectives
    outside_rule = [name for name in lost if rule is not None and name not in rule]
    unconstrained = [name for name in lost if name not in outside_rule]
    if outside_rule:
        notes.append(f"{updater_cls.label} can only minimise {', '.join(rule)}; "
                     f"the model could also minimise {', '.join(outside_rule)}.")
    if unconstrained:
        notes.append(f"Minimising {', '.join(unconstrained)} needs a constraint besides the volume budget, "
                     f"which {updater_cls.label} cannot enforce.")
    if model.constraints and not combined.constraints:
        notes.append(f"{updater_cls.label} enforces only the volume budget, so the model's "
                     f"{', '.join(model.constraints)} constraint is not available.")
    if not model.constraints:
        notes.append(f"{model_cls.label} computes no constraint besides the volume budget.")
    if not model.accepts_filters:
        notes.append(f"{model_cls.label} filters the design itself, so the Filters list is not used.")
    return notes
