# framework/parts/interpolation.py — how density becomes material stiffness.
#
# A density method needs a material law for intermediate densities: an
# interpolation between void (stiffness Emin) and solid (stiffness E0),
#
#     E(ρ) = Emin + f(ρ) · (E0 − Emin),      f(0) = 0,  f(1) = 1,
#
# shaped so that grey material is not worth its cost and the optimum is driven
# towards black and white.  SIMP (f = ρ^p) is the classic choice; RAMP,
# multi-material and other laws are alternatives, and choosing between them is
# a comparison worth making with everything else held fixed — so the law is a
# part of its own, chosen in the solver like the filters:
#
#     solver.interpolation = {"type": "simp", "penal": 3.0}
#
# A physics engine that models material through an interpolation (it declares
# uses_interpolation = True, as the Q4 engine does) asks it for the stiffness
# of every element and for the slope dE/dρ, which every response's sensitivity
# needs.  Both act element-wise on arrays of any shape.

from abc import ABC, abstractmethod

import numpy as np


class Interpolation(ABC):
    """A material law: E(ρ) for every element, and its slope dE/dρ."""

    #: Registry key used in interpolation specs: {"type": name, ...}.  Empty = abstract.
    name = ""
    #: Human-readable name for menus.
    label = ""
    #: When to choose it, in a sentence or two: shown as "When to use it" in its help window.
    use_when = ""
    #: Menu position; lower comes first.
    order = 100
    #: Tunable parameters (framework.params.Param).  The constructor must accept
    #: each one as a keyword argument of the same name.
    params = ()
    #: The problem dimensions it works in; None means any (it never looks at the mesh's shape).
    dims = None
    #: Parameters a schedule may change during a run (framework/parts/schedule.py).
    schedulable = ()
    #: True when the material budget differs from the geometric density sum.
    nonlinear_volume = False

    def setup(self, problem):
        """Bind optional scenario context; ordinary laws need no setup."""

    @classmethod
    def problems_with(cls, physics):
        """Reasons this law cannot be used with a physics engine class."""
        return []

    def volume_density(self, density):
        """Effective material cost per cell; identity for ordinary stiffness laws."""
        return density

    def volume_slope(self, density):
        """Derivative of volume_density, before the filter/representation adjoints."""
        return np.ones_like(density, dtype=float)

    @abstractmethod
    def stiffness(self, density, E0, Emin):
        """Young's modulus of each element, from Emin at density 0 to E0 at density 1."""

    @abstractmethod
    def slope(self, density, E0, Emin):
        """dE/dρ of each element: what every stiffness-based sensitivity is scaled by."""
