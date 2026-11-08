"""framework.parts — the interface of every swappable part.

    method.py          OptimizationMethod: the engine's only view of any method
    composition.py     Model (what is optimised) + Updater (how the design moves) = ComposedMethod
    model.py           Model: a design in, an Evaluation (values and gradients) out
    updater.py         Updater: an Evaluation in, the next design out
    representation.py  Representation: what the design variables are (densities, bars, a network...)
    filter.py          Filter: design variables -> physical density, and the chain rule back
    interpolation.py   Interpolation: the material law, density -> stiffness
    physics.py         Physics: a physics engine that solves a density and answers questions
    response.py        Response: an objective or constraint, with its value and gradient
    variants.py        VariantModel: one design evaluated in several versions (robust formulation)
    schedule.py        Schedule: a parameter that changes during a run (continuation)
    postprocess.py     PostProcessor: what is made of a finished design
"""
