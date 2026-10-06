# framework/parts/representation.py — what the design variables are.
#
# Every density method needs, in the end, a density per element; what it
# optimises need not be that.  It can be the densities themselves, the
# position, size and angle of a few hundred bars (moving morphable
# components), the coefficients of a level-set function, or the weights of a
# neural network.  The representation turns the variables into an element
# density field, and carries the chain rule back:
#
#     variables z ──density(z)──> element field x ──filters──> ρ ──physics──> ...
#     dz <──backward(z, dx)──────── dx <──filter adjoint──── dρ <── ...
#
# It is chosen in the solver like the filters and the material law,
#
#     solver.representation = {"type": "mmc", "n_x": 4, "n_y": 2}
#
# and also says where the design starts (initial()) and how far each variable
# may move (bounds()), since both depend on what the variables are.
#
# `element_wise` says whether the variables ARE element densities.  Some
# update rules (optimality criteria, BESO, SiMPL) only make sense then; they
# declare needs_element_densities, and such a pairing is refused before the
# run with the reason.  Updaters that work on any vector (MMA, GCMMA, SLSQP)
# work with every representation.

from abc import ABC, abstractmethod


class Representation(ABC):
    """Design variables → element density field, and the chain rule back."""

    #: Registry key used in representation specs: {"type": name, ...}.  Empty = abstract.
    name = ""
    #: Human-readable name for menus.
    label = ""
    #: Menu position; lower comes first.
    order = 100
    #: Tunable parameters (framework.params.Param).  The constructor must accept
    #: each one as a keyword argument of the same name.
    params = ()
    #: Parameters a schedule may change during a run (framework/parts/schedule.py).
    schedulable = ()
    #: True when the variables are one density per element (the identity map).
    element_wise = False
    #: One sentence of advice on using it (a suitable move limit, say), shown
    #: before a run and in the GUI; empty when there is none.
    advice = ""

    @abstractmethod
    def setup(self, problem):
        """Prepare for a run on the meshed problem (element positions, the volume fraction, ...)."""

    @abstractmethod
    def initial(self):
        """The start design: the variables' first values."""

    @abstractmethod
    def bounds(self):
        """(lower, upper) for every variable, shaped like the variables."""

    @abstractmethod
    def density(self, z):
        """The (nely, nelx) element density field the variables describe, in [0, 1]."""

    @abstractmethod
    def backward(self, z, sensitivity):
        """d(objective)/dz, given `sensitivity` = d(objective)/d(density(z)), shaped like the field."""
