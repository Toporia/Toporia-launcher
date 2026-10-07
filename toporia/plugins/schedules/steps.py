# plugins/schedules/steps.py — equal steps every so many iterations.
#
# The classic SIMP continuation: p = 1, 1.5, 2, ... 3, raised by 0.5 every 20
# iterations, so each penalty is solved before the next is applied.  The step
# is taken towards `end`, so a decreasing schedule needs no negative step.

from toporia.framework.params import Param
from toporia.framework.parts.schedule import Schedule

from ._common import END, EVERY, START, format_number, towards


class Steps(Schedule):
    """start, start + step, ... every `every` iterations, then `end`."""

    name = "steps"
    label = "Equal steps"
    order = 10
    params = (START, END,
              Param("step", 0.5, "Step", "Change at each step, taken towards the end value.",
                    min=1e-9, max=1e6, step=0.1, decimals=4),
              EVERY)

    def __init__(self, start=1.0, end=3.0, step=0.5, every=20):
        self.start, self.end, self.step, self.every = float(start), float(end), abs(float(step)), int(every)

    def value(self, completed):
        direction = 1.0 if self.end >= self.start else -1.0
        return towards(self.start, self.end, self.start + direction * self.step * (completed // self.every))

    def finished(self, completed):
        return self.value(completed) == self.end

    def describe(self):
        sign = "+" if self.end >= self.start else "-"
        return (f"{format_number(self.start)} -> {format_number(self.end)}, "
                f"{sign}{format_number(self.step)} every {self.every} iterations")
