"""test_schema.py — parameter declarations, plugin registries and parameter paths.

These pin the machinery that lets a plugin describe itself: if they pass, a new
method or filter only has to declare its Params to appear in the GUI, be
sweepable, and be validated before a run.
"""

from dataclasses import fields

import pytest

from toporia.core import (
    OUTPUT_PARAMS,
    SCENARIO_PARAMS,
    SOLVER_PARAMS,
    Output,
    Run,
    Scenario,
    Solver,
    apply_param,
    read_param,
)
from toporia.core.params import Param, resolve_params, select
from toporia.library.catalog import parameter_paths
from toporia.library.filters import FILTERS
from toporia.library.methods import METHODS, make_method
from toporia.library.models import MODELS
from toporia.library.problems import get_run
from toporia.library.updaters import UPDATERS

PLUGINS = [(f"method:{c.name}", c) for c in METHODS.classes()] + \
          [(f"filter:{c.name}", c) for c in FILTERS.classes()] + \
          [(f"model:{c.name}", c) for c in MODELS.classes()] + \
          [(f"updater:{c.name}", c) for c in UPDATERS.classes()]


# ── Param ─────────────────────────────────────────────────────────────────────

def test_kind_is_inferred_from_the_default():
    assert Param("a", 1.0).kind == "float"
    assert Param("b", 3).kind == "int"
    assert Param("c", True).kind == "bool"
    assert Param("d", "x", choices=(("x", "X"), ("y", "Y"))).kind == "choice"


def test_an_invalid_default_fails_at_declaration():
    with pytest.raises(ValueError):
        Param("a", 5.0, min=0.0, max=1.0)


def test_coerce_rounds_integers_and_checks_ranges():
    p = Param("n", 10, min=1, max=100)
    assert p.coerce(32.6) == 33 and isinstance(p.coerce(32.6), int)
    with pytest.raises(ValueError):
        p.coerce(0)


def test_choice_returns_the_declared_value():
    p = Param("direction", 0, choices=((0, "up"), (90, "right")))
    assert p.coerce(90.0) == 90 and isinstance(p.coerce(90.0), int)
    with pytest.raises(ValueError):
        p.coerce(45)


def test_resolve_fills_defaults_and_rejects_unknown_keys():
    declared = (Param("a", 1.0), Param("b", 2))
    assert resolve_params("demo", declared, {"b": 5}) == {"a": 1.0, "b": 5}
    with pytest.raises(ValueError, match=r"demo has no parameter.*'c'.*Available"):
        resolve_params("demo", declared, {"c": 1})


def test_select_picks_in_the_requested_order():
    assert [p.name for p in select(SOLVER_PARAMS + SCENARIO_PARAMS, "volfrac", "m")] == ["volfrac", "m"]


@pytest.mark.parametrize(("declared", "cls"),
                         [(SCENARIO_PARAMS, Scenario), (SOLVER_PARAMS, Solver), (OUTPUT_PARAMS, Output)],
                         ids=["scenario", "solver", "output"])
def test_field_param_defaults_match_the_dataclass(declared, cls):
    defaults = {f.name: f.default for f in fields(cls)}
    for param in declared:
        assert param.default == defaults[param.name], param.name


# ── Registries ────────────────────────────────────────────────────────────────

def test_every_method_is_discovered_in_menu_order():
    assert METHODS.names() == ["density", "density_mma", "levelset", "pymoto", "density_gcmma"]


def test_every_filter_is_discovered_in_menu_order():
    assert FILTERS.names() == ["density", "sensitivity", "heaviside", "am", "routing", "symmetry"]


def test_aliases_and_case_are_accepted():
    assert METHODS.get("mma") is METHODS.get("density_mma")
    assert METHODS.get("DENSITY") is METHODS.get("density")


def test_an_unknown_name_lists_the_alternatives():
    with pytest.raises(ValueError, match=r"Unknown method 'nope'.*density_mma"):
        make_method("nope")


@pytest.mark.parametrize("cls", [c for _, c in PLUGINS], ids=[i for i, _ in PLUGINS])
def test_plugin_declarations_are_well_formed(cls):
    names = [p.name for p in cls.params]
    assert len(names) == len(set(names)), "duplicate parameter names"
    assert cls.label, "every plugin needs a menu label"


@pytest.mark.parametrize("cls", FILTERS.classes(), ids=lambda c: c.name)
def test_filters_accept_every_declared_parameter(cls):
    cls(**resolve_params(cls.name, cls.params, {}))


# ── Parameter paths ───────────────────────────────────────────────────────────

def test_apply_param_routes_each_path_to_its_owner():
    run = get_run("MBB Beam").updated(volfrac=0.3, m=0.5, save_every=0)
    run = apply_param(run, "method.penal", 4.0)
    run = apply_param(run, "filters[0].rmin", 2.5)
    run = apply_param(run, "load_cases[0].Fa", 180.0)
    run = apply_param(run, "max_iter", 42.7)
    assert run.scenario.volfrac == 0.3
    assert run.solver.m == 0.5
    assert run.output.save_every == 0
    assert run.solver.method_params == {"penal": 4.0}
    assert run.solver.filter_specs[0]["rmin"] == 2.5
    assert run.scenario.load_cases[0].Fa == 180.0
    assert run.solver.max_iter == 43


def test_read_param_is_the_inverse_of_apply_param():
    run = get_run("MBB Beam")
    for path, value in [("volfrac", 0.3), ("m", 0.5), ("max_iter", 7), ("method.penal", 4.0),
                        ("filters[0].rmin", 2.5), ("load_cases[0].Fmag", 2.0)]:
        assert read_param(apply_param(run, path, value), path) == value, path
    assert read_param(run, "method.penal") is None   # unset: the method default applies


def test_numeric_fields_keep_their_declared_type():
    run = Run().updated(tol=0, max_iter=12.0)
    assert isinstance(run.solver.tol, float)
    assert isinstance(run.solver.max_iter, int)


def test_apply_param_never_mutates_its_input():
    base = get_run("MBB Beam")
    apply_param(base, "method.penal", 4.0)
    apply_param(base, "filters[0].rmin", 2.5)
    apply_param(base, "load_cases[0].Fa", 0.0)
    assert base.solver.method_params == {}
    assert "rmin" not in base.solver.filter_specs[0]
    assert base.scenario.load_cases[0].Fa == 270.0


def test_apply_param_rejects_unknown_paths():
    with pytest.raises(KeyError):
        apply_param(Run(), "penal", 3.0)          # it is "method.penal"
    with pytest.raises(KeyError):
        apply_param(Run(), "widgets[0].x", 1.0)


def test_a_misspelt_method_parameter_fails_before_computing():
    run = apply_param(get_run("MBB Beam"), "method.pnal", 4.0)
    with pytest.raises(ValueError, match="pnal"):
        METHODS.get(run.solver.method).resolve_params(run.solver)


def test_paths_follow_the_method_capabilities():
    density = [p for _, p in parameter_paths("density", [{"type": "density"}], 1)]
    levelset = [p for _, p in parameter_paths("levelset", [{"type": "density"}], 1)]
    assert {"volfrac", "m", "method.penal", "filters[0].rmin", "load_cases[0].Fmag"} <= set(density)
    assert "method.penal" not in levelset
    assert not any(p.startswith("filters[") for p in levelset)


def _current_value(run, path):
    """The value a path resolves to, falling back to the plugin default when unset."""
    value = read_param(run, path)
    if value is not None:
        return value
    if path.startswith("method."):
        cls = METHODS.get(run.solver.method)
    else:
        index = int(path[len("filters["):path.index("]")])
        cls = FILTERS.get(run.solver.filter_specs[index]["type"])
    return {p.name: p.default for p in cls.params}[path.rsplit(".", 1)[1]]


@pytest.mark.parametrize("method", METHODS.names())
def test_every_offered_path_round_trips_through_validation(method):
    """Every path the GUI offers must be writable and must still validate."""
    run = get_run("MBB Beam").updated(method=method, filter_specs=[{"type": "density"}, {"type": "heaviside"}])
    for _, path in parameter_paths(method, run.solver.filter_specs, len(run.scenario.load_cases)):
        updated = apply_param(run, path, _current_value(run, path))
        METHODS.get(method).resolve_params(updated.solver)
        for spec in updated.solver.filter_specs:
            spec = dict(spec)
            cls = FILTERS.get(spec.pop("type"))
            resolve_params(cls.name, cls.params, spec)
