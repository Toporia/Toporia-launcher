"""plugins.schedules — how a parameter changes during a run (continuation).

Every Schedule subclass in this package with a non-empty `name` is found by
the SCHEDULES registry.  A solver lists them with the parameter each drives:
{"path": "interpolation.penal", "type": "steps", "start": 1, "end": 3}.
See framework/parts/schedule.py.

    steps.py      start, start + step, ... every so many iterations, up to end
    geometric.py  start, start x factor, ... every so many iterations, up to end
    linear.py     a straight ramp from start to end over so many iterations
"""

from toporia.framework.parts.schedule import Schedule
from toporia.framework.registry import Registry

SCHEDULES = Registry("schedule", Schedule, __name__)

__all__ = ["SCHEDULES", "Schedule"]
