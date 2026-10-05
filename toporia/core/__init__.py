"""core — the data model and the contract, and nothing else.

    scenario.py   Scenario: WHAT is solved (domain, supports, loads, material)
    solver.py     Solver:   HOW it is solved (method, parameters, filters, mesh, stopping rule)
    run.py        Run = Scenario + Solver + Output, and parameter paths into it
    problem.py    the geometric problem built from a Scenario at a mesh resolution
    contract.py   the interface every optimisation method implements
    composition.py  a method assembled from a Model (physics) and an Updater (update rule)
    physics.py    the questions a physics engine answers, so responses work on any engine
    flat.py       a Model as an optimiser library sees it: x0, bounds, f, df, g, dg
    external.py   an Updater for a library that runs its own loop, in a background thread
    params.py     self-describing parameter declarations
    responses.py  what a scenario can minimise or constrain, and how it computes itself
    registry.py   plugin discovery
    serialize.py  Scenario / Solver <-> JSON, and fingerprints

Nothing in core imports from toporia.engine, toporia.library or toporia.gui
(the registry looks plugins up by package name, at lookup time).  That one-way
rule is what keeps the data flow readable.
"""

from .composition import ComposedMethod, ConstraintValue, Evaluation, Model, Updater, compose
from .contract import Capabilities, OptimizationMethod
from .external import ExternalOptimizer, Verdict
from .flat import FlatProblem
from .params import Param, resolve_params
from .physics import ELASTIC_ENERGY, STRESS, Physics
from .problem import BaseProblem, RectangularProblem
from .responses import CONSTRAINT_ROLE, OBJECTIVE_ROLE, Response, ResponseValue
from .run import OUTPUT_PARAMS, Output, Run, apply_param, read_param
from .scenario import (
    SCENARIO_PARAMS,
    EdgeConstraint,
    EnforcedArea,
    HoleConfig,
    LoadCase,
    PointConstraint,
    PointLoad,
    Scenario,
)
from .solver import SOLVER_PARAMS, Solver

__all__ = [
    "Scenario", "Solver", "Output", "Run",
    "LoadCase", "HoleConfig", "EdgeConstraint", "PointConstraint", "PointLoad", "EnforcedArea",
    "SCENARIO_PARAMS", "SOLVER_PARAMS", "OUTPUT_PARAMS",
    "apply_param", "read_param",
    "BaseProblem", "RectangularProblem",
    "OptimizationMethod", "Capabilities", "Param", "resolve_params",
    "ComposedMethod", "Model", "Updater", "Evaluation", "ConstraintValue", "compose", "FlatProblem",
    "ExternalOptimizer", "Verdict",
    "Physics", "ELASTIC_ENERGY", "STRESS",
    "Response", "ResponseValue", "OBJECTIVE_ROLE", "CONSTRAINT_ROLE",
]
