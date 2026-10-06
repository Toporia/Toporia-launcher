# framework/parts/filter.py — a filter, and a chain of them.
#
# A filter maps design variables to physical densities and carries the chain
# rule back the other way.  Filters stack into a FilterChain, so a density
# filter, a projection and a fabrication rule can be combined and the
# sensitivities stay consistent through all of them:
#
#     x ──f1.forward──> x1 ──f2.forward──> x2 ── ... ──> physical density
#     dx <─f1.backward── dx1 <─f2.backward── dx2 <── ... ── sensitivity
#
# A filter implements:
#
#   setup(problem, solver)        once, before the run: precompute what is expensive
#   forward(x)                    the design → the filtered field
#   backward(x_in, sensitivity)   the chain rule: d/dx given d/d(forward(x)); x_in is
#                                 the field that entered forward(), for nonlinear filters
#   step(iteration)               once per iteration: advance a continuation schedule
#                                 (Heaviside's β doubling); does nothing by default
#   backward_volume(x_in, s)      the chain rule for the volume's sensitivity; the
#                                 same as backward() unless a filter deliberately
#                                 treats volume differently (the sensitivity filter)
#
# The conformance test (toporia/checks) checks backward() against finite
# differences, unless the filter declares exact_adjoint = False.

from abc import ABC, abstractmethod


class Filter(ABC):
    """Design variables → physical density, and the chain rule back."""

    #: Registry key used in filter specs: {"type": name, ...}.  Empty = abstract.
    name = ""
    #: Human-readable name for menus.
    label = ""
    #: Menu position; lower comes first.
    order = 100
    #: Tunable parameters (framework.params.Param).  The constructor must accept
    #: each one as a keyword argument of the same name.
    params = ()
    #: True when backward() is the exact chain rule of forward().  The
    #: conformance test checks it against finite differences; a heuristic
    #: (the classic sensitivity filter) declares False and is not checked.
    exact_adjoint = True

    def setup(self, problem, solver):
        """Prepare for a run (neighbour weights, masks, ...).  Called once."""

    @abstractmethod
    def forward(self, x):
        """Return the filtered field for design field x."""

    @abstractmethod
    def backward(self, x_in, sensitivity):
        """Return d(objective)/dx, given `sensitivity` = d(objective)/d(forward(x_in))."""

    def step(self, iteration):
        """Advance a continuation schedule, once per iteration.  Does nothing by default."""

    def backward_volume(self, x_in, sensitivity):
        """The chain rule for the volume's sensitivity.  The same as backward() by default."""
        return self.backward(x_in, sensitivity)


class FilterChain:
    """Filters applied in order, with one forward and one backward pass through all of them."""

    def __init__(self, filters):
        self.filters = list(filters)
        self._inputs = []   # the field entering each filter, kept from the last forward pass

    def setup(self, problem, solver):
        for filt in self.filters:
            filt.setup(problem, solver)

    def forward(self, x):
        """Apply every filter left to right, remembering what entered each."""
        self._inputs = []
        for filt in self.filters:
            self._inputs.append(x)
            x = filt.forward(x)
        return x

    def backward(self, sensitivity):
        """Carry a sensitivity back through every filter, right to left."""
        for filt, x_in in zip(reversed(self.filters), reversed(self._inputs)):
            sensitivity = filt.backward(x_in, sensitivity)
        return sensitivity

    def backward_volume(self, sensitivity):
        """Carry the volume's sensitivity back, through each filter's backward_volume."""
        for filt, x_in in zip(reversed(self.filters), reversed(self._inputs)):
            sensitivity = filt.backward_volume(x_in, sensitivity)
        return sensitivity

    def step(self, iteration):
        """Let every filter advance its continuation schedule."""
        for filt in self.filters:
            filt.step(iteration)
