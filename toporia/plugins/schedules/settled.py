# plugins/schedules/settled.py — raised when the design has settled, not on a clock.
#
# Connects to: framework/parts/schedule.py (the Schedule interface and its optional
# observe() hook) and engine/loop.py, which calls observe(iteration, change) after
# every iteration with the design change the method reported.
# The rule: the parameter moves up one level when the design change has been
# below `change_below` for `settle` iterations in a row (and the level has lasted
# at least `min_every` iterations), or at the latest after `max_every` iterations
# at one level.  Without any observation the schedule is simply "every max_every
# iterations", so it is still a sound schedule when nobody tells it the change.
# Why: a fixed clock either raises beta before the design has found its layout or
# wastes iterations on a design that settled long ago; waiting for convergence
# is the usual practice in the projection literature.
# Reference: F. Wang, B. S. Lazarov, O. Sigmund, SMO 43 (2011) 767-784 (beta is
# increased once the design has converged at the current value); J. K. Guest et
# al. use the same idea for their Heaviside continuation.

from toporia.framework.params import Param
from toporia.framework.parts.schedule import Schedule

from ._common import END, START, format_number, towards


class Settled(Schedule):
    """start, then x factor (or + step) each time the design settles, up to end."""

    name = "settled"
    reference = (
        'Continuation raised when the design has settled, common practice in the projection '
        'literature, e.g. F. Wang, B. S. Lazarov and O. Sigmund, Struct. Multidisc. Optim. 43 '
        "(2011) 767-784; Toporia's own rule."
    )
    label = "When the design settles"
    order = 40
    params = (START,
              Param("end", 64.0, "End", "Value it reaches and then keeps.",
                    min=-1e6, max=1e6, step=8.0, decimals=3),
              Param("factor", 2.0, "Factor", "Multiplier at each rise: 2 doubles. Ignored when Step is above 0.",
                    min=1.0001, max=100.0, step=0.5, decimals=3),
              Param("step", 0.0, "Step", "Added at each rise instead of multiplying; 0 = multiply by Factor.",
                    min=0.0, max=1e6, step=0.5, decimals=4),
              Param("change_below", 0.01, "Settled below", "The design change that counts as settled.",
                    min=1e-9, max=1.0, step=0.005, decimals=5),
              Param("settle", 1, "Settled for", "Iterations in a row below the threshold before a rise.",
                    min=1, max=1000, units="iterations"),
              Param("min_every", 10, "At least", "Fewest iterations at one level.", min=1, max=1000, units="iterations"),
              Param("max_every", 50, "At most", "Iterations after which a level is left even if the design has not settled.",
                    min=1, max=10000, units="iterations"))

    def __init__(self, start=1.0, end=64.0, factor=2.0, step=0.0, change_below=0.01,
                 settle=1, min_every=10, max_every=50):
        self.start, self.end, self.factor, self.step = float(start), float(end), float(factor), abs(float(step))
        if self.step == 0 and (self.start <= 0 or self.factor <= 1):
            raise ValueError("multiplying needs a positive start value and a factor above 1 (or give a step)")
        self.change_below, self.settle = float(change_below), int(settle)
        self.min_every, self.max_every = int(min_every), max(int(max_every), int(min_every))
        # (first completed-iteration count at which the value applies, value): the
        # levels so far.  Filled by observe(); extended by the max_every fallback.
        self._levels = [(0, self.start)]
        self._streak = 0

    def _next(self, value):
        up = self.end >= self.start
        if self.step:
            return towards(self.start, self.end, value + (self.step if up else -self.step))
        return towards(self.start, self.end, value * (self.factor if up else 1.0 / self.factor))

    def observe(self, completed, change):
        """Iteration number `completed` has just run with design change `change`."""
        self._streak = self._streak + 1 if change < self.change_below else 0
        began, value = self._levels[-1]
        if began >= completed or value == self.end:
            return                      # already decided for the next iteration, or at the end
        if completed - began >= self.min_every and self._streak >= self.settle:
            self._levels.append((completed, self._next(value)))
            self._streak = 0

    def value(self, completed):
        # Without an observation the level simply ends after max_every iterations.
        while self._levels[-1][1] != self.end and self._levels[-1][0] + self.max_every <= completed:
            began, value = self._levels[-1]
            self._levels.append((began + self.max_every, self._next(value)))
        return next(v for began, v in reversed(self._levels) if began <= completed)

    def finished(self, completed):
        return self.value(completed) == self.end

    def describe(self):
        how = f"+{format_number(self.step)}" if self.step else f"x{format_number(self.factor)}"
        return (f"{format_number(self.start)} -> {format_number(self.end)}, {how} when the change is below "
                f"{format_number(self.change_below)} ({self.min_every}-{self.max_every} iterations per level)")
