# plugins/schedules/linear.py — a straight ramp.
#
# Held at `start` for `after` iterations, then moved in a straight line to
# `end` over `over` iterations: the ramp several fabrication filters use
# (switch the constraint on gradually once a topology has formed).

from toporia.framework.params import Param
from toporia.framework.parts.schedule import Schedule

from ._common import END, START, format_number


class Linear(Schedule):
    """`start` for `after` iterations, then a straight ramp to `end` over `over` iterations."""

    name = "linear"
    label = "Linear ramp"
    order = 30
    params = (START, END,
              Param("after", 0, "Hold for", "Iterations at the start value before the ramp begins.",
                    min=0, max=10000, units="iterations"),
              Param("over", 50, "Ramp over", "Iterations the ramp takes.", min=1, max=10000, units="iterations"))

    def __init__(self, start=1.0, end=3.0, after=0, over=50):
        self.start, self.end, self.after, self.over = float(start), float(end), int(after), int(over)

    def value(self, completed):
        fraction = min(max((completed - self.after) / self.over, 0.0), 1.0)
        return self.end if fraction == 1.0 else self.start + fraction * (self.end - self.start)

    def finished(self, completed):
        return completed >= self.after + self.over

    def describe(self):
        hold = f" after {self.after}" if self.after else ""
        return f"{format_number(self.start)} -> {format_number(self.end)} over {self.over} iterations{hold}"
