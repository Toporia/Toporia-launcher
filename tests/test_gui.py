"""test_gui.py — the generated GUI panels, exercised headlessly.

The GUI builds itself from Param declarations, so these tests check the
generation machinery once for every plugin instead of each panel by hand.
They run with Qt's offscreen platform, so no window ever appears.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from toporia.core import read_param  # noqa: E402
from toporia.core.params import resolve_params  # noqa: E402
from toporia.library.filters import FILTERS  # noqa: E402
from toporia.library.methods import METHODS, method_class, method_classes  # noqa: E402
from toporia.library.models import MODELS  # noqa: E402
from toporia.library.problems import get_run, problem_names  # noqa: E402
from toporia.library.responses import OBJECTIVE_ROLE, responses_for  # noqa: E402
from toporia.library.updaters import UPDATERS  # noqa: E402

PLUGINS = [(f"method:{c.name}", c) for c in METHODS.classes()] + \
          [(f"model:{c.name}", c) for c in MODELS.classes()] + \
          [(f"updater:{c.name}", c) for c in UPDATERS.classes()] + \
          [(f"filter:{c.name}", c) for c in FILTERS.classes()]
METHOD_NAMES = [c.name for c in method_classes()]


def _assert_same(actual, expected):
    assert actual.keys() == expected.keys()
    for key, value in expected.items():
        if isinstance(value, float):
            assert actual[key] == pytest.approx(value, rel=1e-6, abs=1e-9), key
        else:
            assert actual[key] == value, key


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from toporia.gui.window import MainWindow
    return MainWindow()


@pytest.mark.parametrize("cls", [c for _, c in PLUGINS], ids=[i for i, _ in PLUGINS])
def test_param_form_round_trips(app, cls):
    """Defaults, then extreme values, come back out exactly as they went in."""
    from toporia.gui.param_form import ParamForm
    form = ParamForm(cls.params)
    _assert_same(form.get_values(), resolve_params(cls.name, cls.params, {}))

    extremes = {}
    for p in cls.params:
        if p.kind == "choice":
            extremes[p.name] = p.choices[-1][0]
        elif p.is_numeric and p.max is not None:
            extremes[p.name] = p.max
    form.set_values(extremes)
    _assert_same(form.get_values(), resolve_params(cls.name, cls.params, extremes))


@pytest.mark.parametrize("name", METHOD_NAMES)
def test_selecting_a_method_adapts_the_panels(window, name):
    from toporia.gui import runner
    cls = method_class(name)
    window.core.select_method(name)
    assert window.core.method_name() == name

    # Filters are shown exactly when the method uses them; the pipeline says why when not.
    assert window.filters.isHidden() == (not cls.capabilities.accepts_filters)
    if not cls.capabilities.accepts_filters:
        assert any("Filters list" in note for note in window.pipeline.notes())

    cfg = runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg)
    assert cfg.solver.method == name
    cls.resolve_params(cfg.solver)   # the GUI only ever produces parameters the method declares

    offered = [window.sg.param.itemData(i) for i in range(window.sg.param.count())]
    for p in cls.params:
        assert (f"method.{p.name}" in offered) == p.is_numeric
    assert any(path.startswith("filters[") for path in offered) == cls.capabilities.accepts_filters


def test_the_pipeline_names_every_part_of_the_selection(window):
    window._on_config_changed("MBB Beam")
    window.core.select_method("q4+mma")
    stages = dict(window.pipeline.stages())
    assert stages["Physics"] == MODELS.get("q4").label
    assert stages["Updater"] == UPDATERS.get("mma").label
    assert stages["Filters"] == FILTERS.get("density").label

    window.core.select_method("q4+pymoto_mma")
    assert dict(window.pipeline.stages())["Updater"] == UPDATERS.get("pymoto_mma").label
    assert window.pipeline.notes() == []          # nothing is lost with this pairing

    window.core.select_method("q4+oc")
    assert any("enforces only the volume budget" in note for note in window.pipeline.notes())


def test_older_method_names_select_the_parts_they_stand_for(window):
    window.core.select_method("density_mma")
    assert window.core.method_name() == "q4+mma"
    assert (window.core.model.currentData(), window.core.updater.currentData()) == ("q4", "mma")


@pytest.mark.parametrize("preset", problem_names())
def test_a_preset_survives_the_round_trip_through_the_gui(window, preset):
    from toporia.gui import runner
    window._on_config_changed(preset)
    cfg = runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg)
    original = get_run(preset)

    assert cfg.solver.method == method_class(original.solver.method).name
    for key in ("volfrac", "m", "tol"):
        assert read_param(cfg, key) == pytest.approx(read_param(original, key)), key
    assert cfg.solver.max_iter == original.solver.max_iter
    # The pipeline comes back with every parameter made explicit.
    assert [s["type"] for s in cfg.solver.filter_specs] == \
        [s.get("type", "density") for s in original.solver.filter_specs]


@pytest.mark.parametrize("name", METHOD_NAMES)
def test_objective_and_constraints_follow_the_method(window, name):
    capabilities = method_class(name).capabilities
    window.core.select_method(name)
    expected = [cls.name for cls in responses_for(OBJECTIVE_ROLE) if cls.name in capabilities.objectives]
    assert window.objective.offered_types() == expected
    can_constrain = bool(capabilities.constraints) and capabilities.max_constraints != 0
    assert window.constraints.isHidden() == (not can_constrain)


def test_a_constraint_reaches_the_run_only_when_the_method_can_enforce_it(window):
    from toporia.gui import runner
    window._on_config_changed("MBB Beam")
    window.core.select_method("q4+pymoto_mma")
    window.constraints.load_specs([{"type": "stress", "limit": 7.0}])

    def build():
        return runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg,
                                   objective=window.objective, constraints=window.constraints)

    assert build().scenario.constraints == [{"type": "stress", "limit": 7.0, "p": 8.0, "q": 0.5, "adaptive": True}]
    offered = [window.sg.param.itemData(i) for i in range(window.sg.param.count())]
    assert "constraints[0].limit" in offered

    window.core.select_method("q4+oc")
    assert build().scenario.constraints == []          # OC cannot enforce it, so the run never sees it
    window.core.select_method("pymoto")
    assert build().scenario.constraints[0]["limit"] == 7.0   # kept for when it can
    window.constraints.load_specs([])
