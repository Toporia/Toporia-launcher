# filter_base.py — Filter ABC and FilterChain orchestrator
#
# Every filter declares name, label and params (see Filter below), and implements:
#   setup(problem, solver)      — called once, precomputes expensive data
#   forward(x)                  — density field transform: x → xf
#   backward(x_in, sensitivity) — chain-rule adjoint: ds/dx given ds/dxf
#   backward_volume(x_in, s)    — adjoint for the volume sensitivity (dv).
#                                 Defaults to the same as backward().
#                                 SensitivityFilter overrides this to identity
#                                 because dv is not filtered by SensitivityFilter.
#
# FilterChain wires N filters together:
#   forward  applies them left-to-right, storing the x entering each filter
#            so nonlinear backward passes have access to those intermediates.
#   backward applies them right-to-left using the stored intermediates.

from abc import ABC, abstractmethod


class Filter(ABC):
    #: Registry key used in filter specs: {"type": name, ...}.  Empty = abstract.
    name = ""
    #: Human-readable name for menus.
    label = ""
    #: Menu position; lower comes first.
    order = 100
    #: Tunable parameters (core.params.Param).  The constructor must accept each
    #: one as a keyword argument of the same name.
    params = ()

    def setup(self, problem, solver): pass

    @abstractmethod
    def forward(self, x): ...

    @abstractmethod
    def backward(self, x_in, sensitivity): ...

    def backward_volume(self, x_in, sensitivity):
        """Adjoint for volume sensitivity.  Defaults to the same as backward().
        Override in filters where volume sensitivity should NOT be filtered."""
        return self.backward(x_in, sensitivity)


class FilterChain:
    """Ordered sequence of filters with a shared forward / backward pass."""

    def __init__(self, filters):
        self.filters = list(filters)
        self._x_ins  = []   # x entering each filter, stored during forward pass

    def setup(self, problem, solver):
        for f in self.filters:
            f.setup(problem, solver)

    # ── forward / backward ────────────────────────────────────────────────────

    def forward(self, x):
        """Apply all filters left-to-right; store input at each stage."""
        self._x_ins = []
        out = x
        for f in self.filters:
            self._x_ins.append(out)
            out = f.forward(out)
        return out

    def backward(self, sensitivity):
        """Compliance sensitivity: apply adjoints right-to-left."""
        s = sensitivity
        for i in range(len(self.filters) - 1, -1, -1):
            s = self.filters[i].backward(self._x_ins[i], s)
        return s

    def backward_volume(self, sensitivity):
        """Volume sensitivity: apply adjoints right-to-left via backward_volume.
        For SensitivityFilter this leaves dv unchanged; for all other
        filters it is identical to backward()."""
        s = sensitivity
        for i in range(len(self.filters) - 1, -1, -1):
            s = self.filters[i].backward_volume(self._x_ins[i], s)
        return s

    # ── convenience helpers ───────────────────────────────────────────────────

    def step(self, iteration):
        """Per-iteration hook — used by HeavisideFilter for beta continuation."""
        for f in self.filters:
            if hasattr(f, "step"):
                f.step(iteration)

    @property
    def heaviside_filters(self):
        from .filter_heaviside import HeavisideFilter
        return [f for f in self.filters if isinstance(f, HeavisideFilter)]
