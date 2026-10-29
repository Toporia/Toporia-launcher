# plugins/schedules/steps.py — equal steps every so many iterations.
#
# The classic SIMP continuation: p = 1, 1.5, 2, ... 3, raised by 0.5 every 20
# iterations, so each penalty is solved before the next is applied.  The step
# is taken towards `end`, so a decreasing schedule needs no negative step.
# `first` delays the first step, as top99neo's continuation does (beta raised
# from iteration 250 on); 0 means the first step comes after `every` iterations.

from toporia.framework.params import Param
from toporia.framework.parts.schedule import Schedule

from ._common import END, EVERY, START, format_number, towards


class Steps(Schedule):
    """start, start + step, ... every `every` iterations, then `end`."""

    name = "steps"
    label = "Equal steps"
    use_when = "To raise a parameter (penalty, beta) by equal amounts at fixed intervals."
    reference = (
        'The classic SIMP continuation, p raised in steps; see O. Sigmund, J. Petersson, "Numerical'
        ' instabilities in topology optimization", Struct. Optim. 16 (1998) 68-75.'
        ' Papers: https://doi.org/10.1007/BF01214002'
    )
    order = 10
    params = (START, END,
              Param("step", 0.5, "Step", "Change at each step, taken towards the end value.",
                    min=1e-9, max=1e6, step=0.1, decimals=4),
              EVERY,
              Param("first", 0, "First step at", "Iteration of the first step; 0 means after the first interval.",
                    min=0, max=100000, step=1, decimals=0))

    def __init__(self, start=1.0, end=3.0, step=0.5, every=20, first=0):
        self.start, self.end, self.step, self.every = float(start), float(end), abs(float(step)), int(every)
        self.first = int(first) or self.every

    def value(self, completed):
        direction = 1.0 if self.end >= self.start else -1.0
        steps = 0 if completed < self.first else (completed - self.first) // self.every + 1
        return towards(self.start, self.end, self.start + direction * self.step * steps)

    def finished(self, completed):
        return self.value(completed) == self.end

    def describe(self):
        sign = "+" if self.end >= self.start else "-"
        delay = f" from iteration {self.first}" if self.first != self.every else ""
        return (f"{format_number(self.start)} -> {format_number(self.end)}, "
                f"{sign}{format_number(self.step)} every {self.every} iterations{delay}")
