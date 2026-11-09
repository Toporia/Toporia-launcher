# plugins/responses/combined.py — one objective made of several variables.
#
# The objective is a list of terms, each an objective-capable response (compliance,
# volume, peak stress, thermal compliance, ...), and a rule that joins them:
#
#     objective = {"type": "combined", "combine": "sum",
#                  "terms": [{"type": "compliance", "weight": 1.0},
#                            {"type": "peak_stress", "weight": 0.5, "p": 8}]}
#
#   sum         J = Σ wᵢ sᵢ fᵢ / |fᵢ⁰|           weighted sum
#   minmax      J = KS(wᵢ sᵢ fᵢ / |fᵢ⁰|)         a smooth maximum: the worst term is pushed down
#   expression  J = expression(f₁, f₂, ...)       a Python formula over the raw values
#
# fᵢ⁰ is the term's value at the first design, so terms in different units weigh as
# set by wᵢ alone; sᵢ is +1 to minimise a term and −1 to maximise it.  A response that
# already maximises (its label says so, e.g. the fundamental frequency) is maximised
# when minimised.
#
# The smooth maximum is the Kreisselmeier–Steinhauser function
#     KS(a) = max(a) + (1/p) · log Σ exp(p (aᵢ − max(a))),
# within log(n)/p above the true maximum.  It needs no extra variable (a bound
# formulation would), so it works with every updater.
#
# The expression may use the terms' names, numbers, + − * / ** and sqrt, exp, log,
# abs, min, max, sin, cos, tanh.  Its derivative with respect to each term is a
# central difference on the formula alone (a scalar function, so it is cheap and
# accurate); the terms' own gradients are exact, and the chain rule joins them.

import math
import re

import numpy as np

from toporia_core.framework.companions import set_up_response
from toporia_core.framework.params import Param
from toporia_core.framework.parts.response import OBJECTIVE_ROLE, Response, ResponseValue
from toporia_core.framework.variables import compile_expression, formula_slopes

COMBINE_CHOICES = (("sum", "Weighted sum"), ("minmax", "Min-max (smooth worst case)"),
                   ("expression", "Python expression"))
TERM_KEYS = ("weight", "sense", "name", "physics")


def term_names(terms):
    """The name of each term: its own `name`, else its type, numbered when it repeats."""
    names, seen = [], {}
    for term in terms:
        base = term.get("name") or term.get("variable") or term["type"]
        seen[base] = seen.get(base, 0) + 1
        names.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return names


class CombinedObjective(Response):
    """Several variables in one objective: a weighted sum, a smooth worst case, or a formula."""
    name = "combined"
    label = "Combined objective"
    use_when = (
        "When more than one quantity matters, e.g. stiffness and peak stress, or stiffness under two "
        "physics: weigh them, push down the worst one, or write your own formula."
    )
    reference = (
        "Weighted-sum and min-max multi-objective formulations: R. T. Marler, J. S. Arora, Struct."
        " Multidisc. Optim. 26 (2004) 369-395; the KS function: G. Kreisselmeier, R. Steinhauser, IFAC"
        " Proc. 12 (1979) 113-117. Papers: https://doi.org/10.1007/s00158-003-0368-6"
    )
    order = 90
    roles = (OBJECTIVE_ROLE,)
    requires = ()           # each term is checked against the physics when the run starts
    structured = ("terms", "expression")
    params = (
        Param("combine", "sum", "Combine by", "How the terms become one number to minimise.",
              choices=COMBINE_CHOICES),
        Param("ks_p", 40.0, "Min-max sharpness",
              "For min-max: how closely the smooth maximum follows the worst term. Higher is closer "
              "but harder to optimise.", min=1.0, max=500.0, step=5.0, decimals=1),
    )

    @classmethod
    def gradient_check_settings_for(cls, physics):
        """A formula of the physics' own energy and the volume, so the chain rule is checked too."""
        energy = next((name for name in ("compliance", "thermal_compliance")
                       if _computable(name, physics)), "volume")
        return {"combine": "expression", "expression": "main * (1 + volume ** 2)",
                "terms": [{"type": energy, "name": "main"}, {"type": "volume"}]}

    @classmethod
    def validate_spec(cls, values):
        """Check the terms and the expression before a run starts."""
        from toporia_core.framework.registries import resolve_response
        terms = values.get("terms") or []
        if not isinstance(terms, (list, tuple)) or not terms:
            raise ValueError("A combined objective needs at least one term")
        for term in terms:
            if not isinstance(term, dict) or "type" not in term:
                raise ValueError(f"Every term of a combined objective needs a 'type', got {term!r}")
            if term["type"] == cls.name:
                raise ValueError("A combined objective cannot contain another combined objective")
            if term.get("sense", "min") not in ("min", "max"):
                raise ValueError(f"A term's sense is 'min' or 'max', got {term.get('sense')!r}")
            float(term.get("weight", 1.0))
            if term.get("name") and not re.fullmatch(r"[A-Za-z_]\w*", term["name"]):
                raise ValueError(f"A term's name must be a Python name, got {term['name']!r}")
            resolve_response(_response_spec(term), OBJECTIVE_ROLE)
        if values.get("combine") == "expression":
            if not values.get("expression"):
                raise ValueError("Combine by expression needs an expression")
            compile_expression(values["expression"], term_names(terms))

    def setup(self, physics, problem, settings):
        from toporia_core.framework.registries import resolve_response
        super().setup(physics, problem, settings)
        self.names = term_names(settings["terms"])
        self.terms = []
        for term in settings["terms"]:
            term_cls, values = resolve_response(_response_spec(term), OBJECTIVE_ROLE)
            if term.get("physics") is None and not term_cls.computable_on(type(physics)):
                raise ValueError(f"The term {term_cls.label!r} cannot be computed on {physics.label!r}; "
                                 f"it needs the physics features {term_cls.requires}")
            response = set_up_response(term_cls, values, physics, problem, term.get("physics"))
            sign = -1.0 if term.get("sense", "min") == "max" else 1.0
            self.terms.append((response, float(term.get("weight", 1.0)) * sign))
        self.formula = (compile_expression(settings["expression"], self.names)
                        if settings["combine"] == "expression" else None)
        self._reference = None

    def evaluate(self, state, gradient=True):
        results = [response.evaluate(state, gradient=gradient) for response, _ in self.terms]
        values = np.array([r.value for r in results], dtype=float)
        if self._reference is None:
            self._reference = np.where(np.abs(values) > 1e-300, np.abs(values), 1.0)
        reported = {f"term:{name}": float(v) for name, v in zip(self.names, values, strict=True)}
        for result in results:
            reported.update(result.reported)

        combine = self.settings["combine"]
        if combine == "expression":
            value, slopes = self._expression(values)
        else:
            factors = np.array([factor for _, factor in self.terms]) / self._reference
            scaled = factors * values
            if combine == "sum":
                value, slopes = float(np.sum(scaled)), factors
            else:
                p, top = self.settings["ks_p"], float(np.max(scaled))
                weights = np.exp(p * (scaled - top))
                value = top + math.log(float(np.sum(weights))) / p
                slopes = factors * weights / np.sum(weights)
        if not gradient:
            return ResponseValue(value, reported=reported)
        total = sum(slope * r.gradient for slope, r in zip(slopes, results, strict=True))
        return ResponseValue(value, np.asarray(total, dtype=float), reported=reported)

    def _expression(self, values):
        """The formula's value and its slope with respect to each term."""
        value, slopes = formula_slopes(self.formula, dict(zip(self.names, values, strict=True)))
        return value, np.array([slopes[name] for name in self.names])

def _computable(name, physics):
    """True when the response called `name` exists and can compute itself on `physics`."""
    from toporia_core.framework.registries import RESPONSES
    return name in RESPONSES.names() and RESPONSES.get(name).computable_on(physics)


def _response_spec(term):
    """A term without the keys that belong to the combination."""
    return {key: value for key, value in term.items() if key not in TERM_KEYS}
