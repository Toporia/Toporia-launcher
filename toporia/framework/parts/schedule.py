# framework/parts/schedule.py — a parameter that changes during a run.
#
# Many methods only work, or only match their paper, when a parameter is
# tightened as the run goes on: the SIMP penalty raised from 1 to 3, the
# Heaviside sharpness doubled up to 64, a stress p-norm exponent increased once
# the design has settled.  A Schedule says what value a parameter takes after
# a given number of completed iterations, and when it has reached its end:
#
#     solver.schedules = [{"path": "interpolation.penal", "type": "steps",
#                          "start": 1.0, "end": 3.0, "step": 0.5, "every": 20}]
#
# `path` is any parameter path (framework/problem/run.py) whose part allows it
# to change mid-run.  The engine applies every schedule before each iteration,
# records the values with the history, and does not stop on its tolerance
# while a schedule is still moving: a design "converged" at p = 1 is not the
# answer to the problem at p = 3.
#
# Which parameters may change: a part lists them in `schedulable`.  Not every
# parameter can — the density filter's radius is built into its weights when
# the run starts — so a schedule on any other one is refused before the run.
# change_parameter() below sets a value on a live part: through the part's own
# set_parameter(name, value) when it has one (a parameter that other values
# are derived from), else on its `settings` dict (responses) or the attribute
# of the same name.

from abc import ABC, abstractmethod


class Schedule(ABC):
    """The value of one parameter after a number of completed iterations."""

    #: Registry key used in schedule specs: {"type": name, "path": ..., ...}.  Empty = abstract.
    name = ""
    #: Human-readable name for menus.
    label = ""
    #: Menu position; lower comes first.
    order = 100
    #: Tunable parameters (framework.params.Param).  The constructor must accept
    #: each one as a keyword argument of the same name.
    params = ()
    #: The problem dimensions it works in; None means any (it never looks at the mesh's shape).
    dims = None

    @abstractmethod
    def value(self, completed):
        """The parameter's value for the iteration after `completed` finished ones (0 for the first)."""

    @abstractmethod
    def finished(self, completed):
        """True once value() will not change any more."""

    def describe(self):
        """A few words for the Pipeline box, e.g. "1 -> 3, +0.5 every 20 iterations"."""
        return self.label


def change_parameter(part, name, value):
    """Set parameter `name` of a live part to `value`, as a schedule does each iteration."""
    if name not in getattr(part, "schedulable", ()):
        raise ValueError(f"{getattr(part, 'label', type(part).__name__)!r} cannot change {name!r} during a run")
    if hasattr(part, "set_parameter"):
        part.set_parameter(name, value)
    elif isinstance(getattr(part, "settings", None), dict) and name in part.settings:
        part.settings[name] = value
    elif hasattr(part, name):
        setattr(part, name, value)
    else:
        raise TypeError(f"{type(part).__name__} declares {name!r} schedulable but holds no such value; "
                        f"give it a set_parameter(name, value) method")
