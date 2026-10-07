"""test_plugins.py — plugins from outside the repository, and what happens when one is missing.

A plugin package is found through a standard entry point; one that fails to
load must not take the others down; one whose optional dependency is not
installed must be greyed out and refused with an install hint, not fail
part-way through a run; and toporia.api must offer everything a plugin needs.
"""

import sys
import types

import numpy as np
import pytest

import toporia.framework.registry as registry_module
from toporia.framework.parts.updater import Updater
from toporia.framework.registry import Registry, missing_dependencies
from toporia.plugins.updaters import UPDATERS
from toporia.plugins.updaters.oc import OCUpdater

MISSING = "toporia_test_package_that_does_not_exist"


class _EntryPoint:
    """Stands in for importlib.metadata.EntryPoint."""

    def __init__(self, name, value, loaded, dist="my-optimisers"):
        self.name, self.value, self._loaded = name, value, loaded
        self.dist = types.SimpleNamespace(name=dist)

    def load(self):
        if isinstance(self._loaded, Exception):
            raise self._loaded
        return self._loaded


class ExternalStep(OCUpdater):
    """An updater shipped by another package (here: OC under another name)."""
    name, label = "external_step", "External step"


def _plugin_module():
    module = types.ModuleType("my_optimisers.updaters")

    class FromModule(OCUpdater):
        name, label = "from_module", "From a module"

    FromModule.__module__ = module.__name__
    module.FromModule = FromModule
    return module


@pytest.fixture
def installed(monkeypatch):
    """Pretend a package is installed that declares updaters through entry points."""
    points = {
        "toporia.updaters": [
            _EntryPoint("external_step", "my_optimisers:ExternalStep", ExternalStep),
            _EntryPoint("module", "my_optimisers.updaters", _plugin_module()),
            _EntryPoint("broken", "my_optimisers.broken", ImportError("No module named 'nlopt'")),
            _EntryPoint("clash", "my_optimisers:OC", type("OC", (OCUpdater,), {"name": "oc", "label": "x"})),
        ],
    }
    monkeypatch.setattr(registry_module, "_entry_points", lambda group: points.get(group, []))


# ── Entry points ──────────────────────────────────────────────────────────────

def test_an_installed_package_adds_its_plugins(installed):
    registry = Registry("updater", Updater, "toporia.plugins.updaters")
    assert {"external_step", "from_module", "oc", "mma"} <= set(registry.names())
    assert registry.source("external_step") == "my-optimisers"
    assert registry.source("oc") == "toporia"


def test_a_broken_or_clashing_plugin_is_reported_and_the_rest_still_load(installed):
    registry = Registry("updater", Updater, "toporia.plugins.updaters")
    errors = dict(registry.errors)
    assert "No module named 'nlopt'" in errors["broken = my_optimisers.broken"]
    assert "Two updaters are named 'oc'" in errors["clash = my_optimisers:OC"]
    assert registry.get("oc") is OCUpdater                 # the built-in one is kept
    assert "external_step" in registry.names()


def test_a_broken_module_in_a_package_does_not_hide_the_others(tmp_path, monkeypatch):
    package = tmp_path / "toporia_test_plugins"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "good.py").write_text(
        "from toporia.plugins.updaters.oc import OCUpdater\n"
        "class Good(OCUpdater):\n    name, label = 'good', 'Good'\n")
    (package / "bad.py").write_text("import toporia_test_package_that_does_not_exist\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    registry = Registry("updater", Updater, "toporia_test_plugins")
    assert registry.names() == ["good"]
    assert [where for where, _ in registry.errors] == ["toporia_test_plugins.bad"]
    sys.modules.pop("toporia_test_plugins", None)


def test_an_installed_updater_is_a_method_part_like_any_other(installed):
    from toporia.engine.loop import initialized_method
    from toporia.plugins.methods import method_class
    from toporia.plugins.problems import get_run
    UPDATERS._by_name = None        # rediscover with the package installed
    try:
        assert method_class("q4+external_step").updater is ExternalStep
        run = get_run("MBB Beam").updated(method="q4+external_step", m=0.3, max_iter=2, tol=0.0)
        method = initialized_method(run)
        method.step(1)
        assert np.all(np.isfinite(method.get_density()))
    finally:
        UPDATERS._by_name = None    # and forget it again once the fixture is undone


def test_a_run_records_which_package_each_part_came_from(installed, tmp_path):
    import json

    from toporia.engine.loop import run_single
    from toporia.engine.pipeline import pipeline_stages
    from toporia.plugins.problems import get_run
    UPDATERS._by_name = None
    try:
        run = get_run("MBB Beam").updated(method="q4+external_step", m=0.3, max_iter=2, tol=0.0,
                                          save_every=0).with_output_dir(tmp_path)
        # Shown where the parts are shown ...
        assert dict(pipeline_stages(run))["Updater"] == "External step (from my-optimisers)"
        # ... and recorded with the result.
        run_single(run)
        parts = {p["name"]: p for p in json.loads((tmp_path / "run.json").read_text())["parts"]}
        assert parts["external_step"]["source"] == "my-optimisers"
        assert parts["external_step"]["class"].endswith("test_plugins.ExternalStep")
        assert parts["q4"]["source"] == "toporia" and parts["q4"]["version"]
        assert [p["kind"] for p in parts.values()] == ["model", "updater", "representation", "interpolation",
                                                       "filter", "response"]
    finally:
        UPDATERS._by_name = None


def test_a_part_registered_by_hand_says_so():
    from toporia.engine.pipeline import part_origin
    UPDATERS.register(_NeedsMissing)
    try:
        assert part_origin("updater", _NeedsMissing)["source"].startswith("registered by hand")
    finally:
        UPDATERS.unregister(_NeedsMissing.name)


# ── Optional dependencies ─────────────────────────────────────────────────────

class _NeedsMissing(OCUpdater):
    name, label = "needs_missing", "Needs a missing package"
    dependencies = (MISSING,)


@pytest.fixture
def needs_missing():
    UPDATERS.register(_NeedsMissing)
    yield _NeedsMissing
    UPDATERS.unregister(_NeedsMissing.name)


def test_missing_dependencies_are_found_for_a_plugin_and_for_a_pairing(needs_missing):
    from toporia.plugins.methods import method_class
    assert missing_dependencies(needs_missing) == [MISSING]
    assert missing_dependencies(method_class("q4+needs_missing")) == [MISSING]
    assert missing_dependencies(OCUpdater) == []


def test_a_run_refuses_a_missing_dependency_before_it_starts(needs_missing):
    from toporia.engine.loop import initialized_method
    from toporia.plugins.problems import get_run
    run = get_run("MBB Beam").updated(method="q4+needs_missing", m=0.3)
    with pytest.raises(ImportError, match=f"pip install {MISSING}"):
        initialized_method(run)


def test_the_gui_greys_out_what_is_not_installed_and_says_why(needs_missing):
    pytest.importorskip("PySide6.QtWidgets")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from toporia.apps.gui.window import MainWindow

    window = MainWindow()
    combo = window.core.updater
    index = combo.findData("needs_missing")
    item = combo.model().item(index)
    assert not item.isEnabled()
    assert MISSING in item.text() and f"pip install {MISSING}" in item.toolTip()
    assert combo.model().item(combo.findData("oc")).isEnabled()

    window.core.select_method("q4+needs_missing")      # e.g. from a preset written elsewhere
    assert any("Not installed here" in note for note in window.pipeline.notes())
    window.close()


# ── The public API ────────────────────────────────────────────────────────────

def test_the_api_offers_everything_a_plugin_needs():
    import toporia.api as api
    for name in api.__all__:
        assert hasattr(api, name), name
    assert set(api.REGISTRIES) == {"model", "updater", "representation", "filter", "interpolation",
                                     "response", "schedule", "method", "postprocessor"}
    assert api.plugin_errors() == []         # every plugin in this repository loads


def test_entry_point_groups_follow_the_plugin_kinds():
    import toporia.api as api
    assert {kind: registry.group for kind, registry in api.REGISTRIES.items()} == {
        "model": "toporia.models", "updater": "toporia.updaters", "representation": "toporia.representations",
        "filter": "toporia.filters", "schedule": "toporia.schedules",
        "interpolation": "toporia.interpolations", "response": "toporia.responses", "method": "toporia.methods",
        "postprocessor": "toporia.postprocessors"}
