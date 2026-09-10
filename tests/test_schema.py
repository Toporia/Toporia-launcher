"""test_schema.py — parameter declarations, plugin registries and parameter paths.

These pin the machinery that lets a plugin describe itself: if they pass, a new
method or filter only has to declare its Params to appear in the GUI, be
sweepable, and be validated before a run.
"""

from dataclasses import fields, replace

import pytest

from toporia.core.config import CONFIG_PARAMS, TopOptConfig, apply_param
from toporia.core.params import Param, resolve_params
from toporia.library.catalog import parameter_paths
from toporia.library.methods import METHODS, make_method
from toporia.library.methods.filters import FILTERS
from toporia.library.problems import get_config

PLUGINS = [(f"method:{c.name}", c) for c in METHODS.classes()] + \
          [(f"filter:{c.name}", c) for c in FILTERS.classes()]


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


# ── Registries ────────────────────────────────────────────────────────────────

def test_every_method_is_discovered_in_menu_order():
    assert METHODS.names() == ["density", "density_mma", "levelset", "pymoto"]


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


def test_scenario_param_defaults_match_the_dataclass():
    defaults = {f.name: f.default for f in fields(TopOptConfig)}
    for param in CONFIG_PARAMS:
        assert param.default == defaults[param.name], param.name


# ── Parameter paths ───────────────────────────────────────────────────────────

def test_apply_param_writes_every_kind_of_path():
    cfg = get_config("MBB Beam")
    cfg = apply_param(cfg, "volfrac", 0.3)
    cfg = apply_param(cfg, "method.penal", 4.0)
    cfg = apply_param(cfg, "filters[0].rmin", 2.5)
    cfg = apply_param(cfg, "load_cases[0].Fa", 180.0)
    cfg = apply_param(cfg, "max_iter", 42.7)
    assert cfg.volfrac == 0.3
    assert cfg.method_params == {"penal": 4.0}
    assert cfg.filter_specs[0]["rmin"] == 2.5
    assert cfg.load_cases[0].Fa == 180.0
    assert cfg.max_iter == 43


def test_apply_param_never_mutates_its_input():
    base = get_config("MBB Beam")
    apply_param(base, "method.penal", 4.0)
    apply_param(base, "filters[0].rmin", 2.5)
    assert base.method_params == {}
    assert "rmin" not in base.filter_specs[0]


def test_apply_param_rejects_unknown_paths():
    cfg = TopOptConfig()
    with pytest.raises(KeyError):
        apply_param(cfg, "penal", 3.0)          # moved: it is now "method.penal"
    with pytest.raises(KeyError):
        apply_param(cfg, "widgets[0].x", 1.0)


def test_a_misspelt_method_parameter_fails_before_computing():
    cfg = apply_param(get_config("MBB Beam"), "method.pnal", 4.0)
    with pytest.raises(ValueError, match="pnal"):
        METHODS.get(cfg.method).resolve_params(cfg)


def test_paths_follow_the_method_capabilities():
    density = [p for _, p in parameter_paths("density", [{"type": "density"}], 1)]
    levelset = [p for _, p in parameter_paths("levelset", [{"type": "density"}], 1)]
    assert {"volfrac", "method.penal", "filters[0].rmin", "load_cases[0].Fmag"} <= set(density)
    assert "method.penal" not in levelset
    assert not any(p.startswith("filters[") for p in levelset)


def _current_value(cfg, path):
    """The value a path currently resolves to, including plugin defaults."""
    if path.startswith("method."):
        cls = METHODS.get(cfg.method)
        return resolve_params(cls.name, cls.params, cfg.method_params)[path[len("method."):]]
    if path.startswith("filters["):
        index, name = int(path[8:path.index("]")]), path.split(".", 1)[1]
        spec = dict(cfg.filter_specs[index])
        cls = FILTERS.get(spec.pop("type"))
        return resolve_params(cls.name, cls.params, spec)[name]
    if path.startswith("load_cases["):
        index, name = int(path[11:path.index("]")]), path.split(".", 1)[1]
        return getattr(cfg.load_cases[index], name)
    return getattr(cfg, path)


@pytest.mark.parametrize("method", METHODS.names())
def test_every_offered_path_round_trips_through_validation(method):
    """Every path the GUI offers must be writable and must still validate."""
    cfg = replace(get_config("MBB Beam"), method=method,
                  filter_specs=[{"type": "density"}, {"type": "heaviside"}])
    for _, path in parameter_paths(method, cfg.filter_specs, len(cfg.load_cases)):
        updated = apply_param(cfg, path, _current_value(cfg, path))
        METHODS.get(method).resolve_params(updated)
        for spec in updated.filter_specs:
            spec = dict(spec)
            cls = FILTERS.get(spec.pop("type"))
            resolve_params(cls.name, cls.params, spec)
