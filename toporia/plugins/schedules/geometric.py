# plugins/schedules/geometric.py — multiplied by a factor every so many iterations.
#
# The Heaviside continuation of Guest, Prevost & Belytschko (2004) and of
# most projection papers since: beta = 1, 2, 4, ... 64, doubled every 50
# iterations, so the projection sharpens only once the design has settled.

from toporia.framework.params import Param
from toporia.framework.parts.schedule import Schedule

from ._common import START, format_number, towards


class Geometric(Schedule):
    """start, start x factor, start x factor^2, ... every `every` iterations, then `end`."""

    name = "geometric"
    label = "Multiply by a factor"
    order = 20
    params = (START,
              Param("end", 64.0, "End", "Value it reaches and then keeps.",
                    min=1e-9, max=1e6, step=8.0, decimals=3),
              Param("factor", 2.0, "Factor", "Multiplier at each step: 2 doubles.",
                    min=1.0001, max=100.0, step=0.5, decimals=3),
              Param("every", 50, "Every", "Iterations between changes.", min=1, max=1000, units="iterations"))

    def __init__(self, start=1.0, end=64.0, factor=2.0, every=50):
        if float(start) <= 0:
            raise ValueError("a geometric schedule needs a positive start value")
        self.start, self.end, self.factor, self.every = float(start), float(end), float(factor), int(every)

    def value(self, completed):
        steps = completed // self.every
        factor = self.factor if self.end >= self.start else 1.0 / self.factor
        return towards(self.start, self.end, self.start * factor ** steps)

    def finished(self, completed):
        return self.value(completed) == self.end

    def describe(self):
        return (f"{format_number(self.start)} -> {format_number(self.end)}, "
                f"x{format_number(self.factor)} every {self.every} iterations")
