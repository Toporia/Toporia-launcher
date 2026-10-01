"""library.models — what is optimised.

A model turns a design into an objective, a material volume and the gradients
of both (see core.composition.Model).  It owns the physics, the filters and the
sensitivity analysis; it knows nothing about how the design is then updated.

Every Model subclass in this package with a non-empty `name` is found by the
MODELS registry.  Modules starting with an underscore are not scanned.

    q4_compliance.py      compliance with Toporia's 2-D Q4 solver and filter pipeline
    pymoto_elastic.py     linear elasticity on a pyMOTO network: compliance, volume,
                          stress constraints (optional dependency)
"""

from toporia.core.composition import Model
from toporia.core.registry import Registry

MODELS = Registry("model", Model, __name__)

__all__ = ["MODELS"]
