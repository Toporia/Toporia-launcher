# framework/problem/run.py — one complete, runnable job: a Scenario, a Solver and an Output.
#
#     Scenario  (what is solved)  ─┐
#     Solver    (how it is solved) ─┼─>  Run  ─>  engine.loop.run_single(run)
#     Output    (where it goes)    ─┘
#
# A Run is what the engine consumes and what every analysis mode varies.
# Parameter paths address single values inside it:
#
#     "volfrac"             a field of the Scenario, Solver or Output
#     "method.move"         a parameter of the selected method
#     "filters[1].beta"     a parameter of the second filter
#     "load_cases[0].Fmag"  a field of the first load case
#     "objective.<param>"   a parameter of the scenario's objective
#     "interpolation.<param>"  a parameter of the material law (e.g. interpolation.penal)
#     "representation.<param>" a parameter of the design representation (e.g. representation.n_x)
#     "constraints[0].limit" a parameter of the first scenario constraint
#     "schedules[0].end"     a value of the first continuation schedule
#
# apply_param writes one; read_param reads one.  Plain field names are unique
# across Scenario, Solver and Output (checked below), so a path never needs to
# say which of the three it belongs to.

import re
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

from toporia.framework.params import Param
from toporia.framework.problem.scenario import Scenario
from toporia.framework.problem.solver import Solver

# Resolved once at import time so results land in the repository's results/
# folder regardless of where the terminal is opened.
PROJECT_ROOT = Path(__file__).resolve().parents[3]   # toporia/framework/problem/run.py


@dataclass(frozen=True)
class Output:
    """Where results are written.

    Not part of what a run *is*: the same scenario and solver give the same
    result wherever it is saved, so Output is never serialised or fingerprinted.
    """
    dir: Path = PROJECT_ROOT / "results"
    save_every: int = 10   # intermediate density PNG every N iterations (0 = final only)
    # What is made of the final design, in order, each {"type": <name>, <param>: <value>}:
    # a black-and-white version, checks, exports.  Empty: nothing.  See
    # framework/parts/postprocess.py.
    postprocess: list = field(default_factory=list)


OUTPUT_PARAMS = (
    Param("save_every", 10, "Save every N",
          "Save an intermediate density image every N iterations. Use 0 for final only.",
          min=0, max=1000),
)


@dataclass(frozen=True)
class Run:
    """A scenario, the solver to apply to it, and where to put the results."""
    scenario: Scenario = field(default_factory=Scenario)
    solver: Solver = field(default_factory=Solver)
    output: Output = field(default_factory=Output)

    def with_output_dir(self, directory):
        """Return a copy that writes its results to `directory`."""
        return replace(self, output=replace(self.output, dir=Path(directory)))

    def updated(self, **values):
        """Return a copy with several parameter paths set, e.g. run.updated(volfrac=0.3, m=0.5)."""
        run = self
        for path, value in values.items():
            run = apply_param(run, path, value)
        return run


# ── Parameter paths ───────────────────────────────────────────────────────────

_PARTS = {"scenario": Scenario, "solver": Solver, "output": Output}
_OWNER = {f.name: part for part, cls in _PARTS.items() for f in fields(cls)}
if len(_OWNER) != sum(len(fields(cls)) for cls in _PARTS.values()):
    raise RuntimeError("Scenario, Solver and Output must not share field names: "
                       "plain parameter paths would become ambiguous")

_INDEXED_PATH = re.compile(r"^(?P<collection>\w+)\[(?P<index>\d+)\]\.(?P<field>\w+)$")
_METHOD_PREFIX = "method."
_OBJECTIVE_PREFIX = "objective."
_INTERPOLATION_PREFIX = "interpolation."
_REPRESENTATION_PREFIX = "representation."


def _owner(path):
    """Return the name of the part ("scenario", "solver", "output") owning a plain field."""
    try:
        return _OWNER[path]
    except KeyError:
        raise KeyError(f"Unknown parameter path {path!r}") from None


def _coerce(field_type, value):
    """Keep numeric fields in their declared type; sweeps generate floats, JSON gives ints."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if field_type in (int, "int"):
        return int(round(value))
    if field_type in (float, "float"):
        return float(value)
    return value


def apply_param(run, path: str, value):
    """Return a NEW Run with the value at one parameter path replaced.

    Method and filter parameter names are not checked here, because core does
    not know which plugins exist.  They are validated when the run starts,
    against the Param declarations on the plugin classes, so a typo still fails
    before any computation.  toporia.plugins.catalog.parameter_paths lists the
    valid paths for a given run.

    The original run is never modified: sweeps rely on the base run staying
    unchanged across every cell.
    """
    if path.startswith(_METHOD_PREFIX):
        name = path[len(_METHOD_PREFIX):]
        solver = replace(run.solver, method_params={**run.solver.method_params, name: value})
        return replace(run, solver=solver)
    if path.startswith(_OBJECTIVE_PREFIX):
        name = path[len(_OBJECTIVE_PREFIX):]
        return replace(run, scenario=replace(run.scenario, objective={**run.scenario.objective, name: value}))
    if path.startswith(_INTERPOLATION_PREFIX):
        name = path[len(_INTERPOLATION_PREFIX):]
        return replace(run, solver=replace(run.solver, interpolation={**run.solver.interpolation, name: value}))
    if path.startswith(_REPRESENTATION_PREFIX):
        name = path[len(_REPRESENTATION_PREFIX):]
        return replace(run, solver=replace(run.solver, representation={**run.solver.representation, name: value}))

    match = _INDEXED_PATH.match(path)
    if match:
        collection, index, field_name = match["collection"], int(match["index"]), match["field"]
        if collection == "filters":
            specs = [dict(spec) for spec in run.solver.filter_specs]
            specs[index][field_name] = value
            return replace(run, solver=replace(run.solver, filter_specs=specs))
        if collection == "constraints":
            specs = [dict(spec) for spec in run.scenario.constraints]
            specs[index][field_name] = value
            return replace(run, scenario=replace(run.scenario, constraints=specs))
        if collection == "schedules":
            specs = [dict(spec) for spec in run.solver.schedules]
            specs[index][field_name] = value
            return replace(run, solver=replace(run.solver, schedules=specs))
        if collection == "load_cases":
            cases = list(run.scenario.load_cases)
            cases[index] = replace(cases[index], **{field_name: value})
            return replace(run, scenario=replace(run.scenario, load_cases=cases))
        raise KeyError(f"Unknown parameter collection {collection!r} in path {path!r}")

    part = _owner(path)
    current = getattr(run, part)
    field_type = next(f.type for f in fields(current) if f.name == path)
    return replace(run, **{part: replace(current, **{path: _coerce(field_type, value)})})


def read_param(run, path: str):
    """Return the value at a parameter path — the inverse of apply_param.

    For a method parameter that has not been set, returns None: the method's
    declared default applies, and only the method class knows what that is.
    """
    if path.startswith(_METHOD_PREFIX):
        return run.solver.method_params.get(path[len(_METHOD_PREFIX):])
    if path.startswith(_OBJECTIVE_PREFIX):
        return run.scenario.objective.get(path[len(_OBJECTIVE_PREFIX):])
    if path.startswith(_INTERPOLATION_PREFIX):
        return run.solver.interpolation.get(path[len(_INTERPOLATION_PREFIX):])
    if path.startswith(_REPRESENTATION_PREFIX):
        return run.solver.representation.get(path[len(_REPRESENTATION_PREFIX):])

    match = _INDEXED_PATH.match(path)
    if match:
        collection, index, field_name = match["collection"], int(match["index"]), match["field"]
        if collection == "filters":
            return run.solver.filter_specs[index].get(field_name)
        if collection == "constraints":
            return run.scenario.constraints[index].get(field_name)
        if collection == "schedules":
            return run.solver.schedules[index].get(field_name)
        if collection == "load_cases":
            return getattr(run.scenario.load_cases[index], field_name)
        raise KeyError(f"Unknown parameter collection {collection!r} in path {path!r}")

    return getattr(getattr(run, _owner(path)), path)
