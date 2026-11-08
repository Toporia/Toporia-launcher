"""Portable, typed nested workflow contract for GUI composition.

Only optimization, sequential restriction and completed-branch Boolean
composition are executable. Export is the implicit mandatory terminal function.
No arbitrary code, cyclic wiring or coupled solve is accepted by this format.
"""

import re
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

from .files import from_dict, to_dict
from .scenario import Scenario
from .solver import Solver

SCENARIO_FIELDS = {"objective", "constraints", "volfrac", "load_cases"}


def optimization(name="Optimization"):
    return {"id": "n" + uuid4().hex[:12], "kind": "optimization", "name": name}


def nodes(tree):
    yield tree
    for child in tree.get("children", []):
        yield from nodes(child)


def validate_workflow(tree):
    """Reject ambiguous, unsafe or unsupported structures before activating them."""
    seen = set()

    def check(node, depth):
        if depth > 12 or len(seen) >= 64:
            raise ValueError("Workflow supports at most 64 functions and 12 nested levels")
        if not isinstance(node, dict) or set(node) - {"id", "kind", "name", "children", "operation", "settings"}:
            raise ValueError("Unknown workflow function fields")
        key, kind = node.get("id"), node.get("kind")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", key) or key in seen:
            raise ValueError("Workflow function IDs must be unique, safe names")
        seen.add(key)
        if not isinstance(node.get("name"), str) or not node["name"].strip():
            raise ValueError("Each workflow function needs a name")
        if kind == "optimization":
            if "children" in node or "operation" in node:
                raise ValueError("Optimization functions cannot contain composition children")
            settings = node.get("settings", {})
            if not isinstance(settings, dict) or set(settings) - {"solver", "scenario"}:
                raise ValueError("Unknown optimization settings")
            if "solver" in settings:
                if not isinstance(settings["solver"], dict):
                    raise ValueError("Optimization solver settings must be a dictionary")
                from_dict(Solver, settings["solver"])
            if "scenario" in settings:
                if not isinstance(settings["scenario"], dict) or set(settings["scenario"]) - SCENARIO_FIELDS:
                    raise ValueError("All workflow stages must share the operating domain")
                from_dict(Scenario, settings["scenario"])
        elif kind in {"sequential", "parallel"}:
            if "settings" in node:
                raise ValueError("Composition settings belong to their optimization functions")
            children = node.get("children")
            if not isinstance(children, list) or len(children) < 2:
                raise ValueError("Composition requires at least two child functions")
            if kind == "parallel":
                if node.get("operation", "union") not in {"union", "intersection", "difference"}:
                    raise ValueError("Unknown Boolean combination operation")
            elif "operation" in node:
                raise ValueError("Sequential transformation is fixed to previous-volume restriction")
            for child in children:
                check(child, depth + 1)
        else:
            raise ValueError(f"Unsupported workflow function: {kind}")

    check(tree, 0)
    return tree


def stage_settings(run):
    scenario = to_dict(run.scenario)
    return {"solver": to_dict(run.solver), "scenario": {key: scenario[key] for key in SCENARIO_FIELDS}}


def stage_run(base, node):
    """Stage-specific physics/solver/responses on the shared physical mesh."""
    settings = node.get("settings", {})
    solver = from_dict(Solver, settings["solver"]) if "solver" in settings else base.solver
    # Mesh resolution is an operating-space property shared by all branches.
    solver = replace(solver, m=base.solver.m)
    scenario = {**to_dict(base.scenario), **deepcopy(settings.get("scenario", {}))}
    return replace(base, scenario=from_dict(Scenario, scenario), solver=solver)
