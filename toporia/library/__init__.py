"""library — the swappable parts.

Everything here is an *implementation* that the engine selects at run time:
finite element solvers (fe/), optimisation algorithms and filters (methods/),
and benchmark problem definitions (problems/).

Adding a new method, filter or problem means adding a file in here.  It should
never require editing core/ or engine/.
"""
