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
from toporia.library.methods import METHODS  # noqa: E402
from toporia.library.problems import get_run, problem_names  # noqa: E402

PLUGINS = [(f"method:{c.name}", c) for c in METHODS.classes()] + \
          [(f"filter:{c.name}", c) for c in FILTERS.classes()]


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


@pytest.mark.parametrize("name", METHODS.names())
def test_selecting_a_method_adapts_the_panels(window, name):
    from toporia.gui import runner
    cls = METHODS.get(name)
    window.core.method.setCurrentIndex(window.core.method.findData(name))

    # Filters are shown exactly when the method uses them — no warning label.
    assert window.filters.isHidden() == (not cls.capabilities.accepts_filters)

    cfg = runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg)
    assert cfg.solver.method == name
    cls.resolve_params(cfg.solver)   # the GUI only ever produces parameters the method declares

    offered = [window.sg.param.itemData(i) for i in range(window.sg.param.count())]
    for p in cls.params:
        assert (f"method.{p.name}" in offered) == p.is_numeric
    assert any(path.startswith("filters[") for path in offered) == cls.capabilities.accepts_filters


@pytest.mark.parametrize("preset", problem_names())
def test_a_preset_survives_the_round_trip_through_the_gui(window, preset):
    from toporia.gui import runner
    window._on_config_changed(preset)
    cfg = runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg)
    original = get_run(preset)

    assert cfg.solver.method == METHODS.get(original.solver.method).name
    for key in ("volfrac", "m", "tol"):
        assert read_param(cfg, key) == pytest.approx(read_param(original, key)), key
    assert cfg.solver.max_iter == original.solver.max_iter
    # The pipeline comes back with every parameter made explicit.
    assert [s["type"] for s in cfg.solver.filter_specs] == \
        [s.get("type", "density") for s in original.solver.filter_specs]
