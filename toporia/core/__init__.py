"""core — the contract, and nothing else.

This package defines *what* a topology-optimisation run is: its configuration,
its problem (geometry and boundary conditions), and the interface an algorithm
must implement.  It contains no algorithms, no analysis modes, and no UI.

Nothing in core imports from toporia.engine, toporia.library or toporia.gui.
That one-way rule is what keeps the data flow readable.
"""

from .config import (
    EdgeConstraint,
    EnforcedArea,
    HoleConfig,
    LoadCase,
    PointConstraint,
    PointLoad,
    TopOptConfig,
)
from .contract import Capabilities, OptimizationMethod
from .params import Param, resolve_params
from .problem import BaseProblem, RectangularProblem

__all__ = [
    "TopOptConfig", "LoadCase", "HoleConfig", "EdgeConstraint",
    "PointConstraint", "PointLoad", "EnforcedArea",
    "BaseProblem", "RectangularProblem",
    "OptimizationMethod", "Capabilities", "Param", "resolve_params",
]
