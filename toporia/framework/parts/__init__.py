"""framework.parts — the interface of every swappable part.

    method.py       OptimizationMethod: the engine's only view of any method
    composition.py  Model (what is optimised) + Updater (how the design moves) = ComposedMethod
    physics.py      Physics: a physics engine that solves a density and answers questions
    response.py     Response: an objective or constraint, with its value and gradient
    filter.py       Filter: design variables -> physical density, and the chain rule back
"""
