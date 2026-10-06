# plugins/schedules/_common.py — the values every schedule shares.

from toporia.framework.params import Param

START = Param("start", 1.0, "Start", "Value for the first iteration.",
              min=-1e6, max=1e6, step=0.5, decimals=3)
END = Param("end", 3.0, "End", "Value it reaches and then keeps.",
            min=-1e6, max=1e6, step=0.5, decimals=3)
EVERY = Param("every", 20, "Every", "Iterations between changes.", min=1, max=1000, units="iterations")


def towards(start, end, value):
    """`value`, but not beyond `end` in the direction from `start`."""
    return min(value, end) if end >= start else max(value, end)


def format_number(value):
    return f"{value:g}"
