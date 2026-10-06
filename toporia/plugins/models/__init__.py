"""library.models — what is optimised.

A model turns a design into an objective, a material volume, the scenario's
constraints and the gradients of all of them (see core.composition.Model).  It
owns the physics, the filters and the sensitivity analysis; it knows nothing
about how the design is then updated.

There are two ways to write one:

  * assembled from parts (assembled.py): name a physics engine (core/physics.py)
    and the filters and responses come for free — every response the engine
    provides features for, every filter in the pipeline;
  * by hand, as a whole, when the physics brings its own filters and gradients
    (pyMOTO's network, which backpropagates).

Every Model subclass in this package with a non-empty `name` is found by the
MODELS registry.  Modules starting with an underscore are not scanned.

    assembled.py          the generic model: filters + physics engine + responses
    q4.py                 Toporia's 2-D Q4 solver: compliance, volume, stress
    pymoto_elastic.py     linear elasticity on a pyMOTO network: compliance, volume,
                          stress constraints (optional dependency)
"""

from toporia.framework.parts.composition import Model
from toporia.framework.registry import Registry

MODELS = Registry("model", Model, __name__)

__all__ = ["MODELS"]
