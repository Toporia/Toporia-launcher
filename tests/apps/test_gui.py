"""test_gui.py — the generated GUI panels, exercised headlessly.

The GUI builds itself from Param declarations, so these tests check the
generation machinery once for every plugin instead of each panel by hand.
They run with Qt's offscreen platform, so no window ever appears.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from toporia.framework import read_param  # noqa: E402
from toporia.framework.params import resolve_params  # noqa: E402
from toporia.plugins.filters import FILTERS  # noqa: E402
from toporia.plugins.methods import METHODS, method_class, method_classes  # noqa: E402
from toporia.plugins.models import MODELS  # noqa: E402
from toporia.plugins.problems import get_run, problem_names  # noqa: E402
from toporia.plugins.responses import OBJECTIVE_ROLE, responses_for  # noqa: E402
from toporia.plugins.updaters import UPDATERS  # noqa: E402

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
    from toporia.apps.gui.window import MainWindow
    return MainWindow()


@pytest.mark.parametrize("cls", [c for _, c in PLUGINS], ids=[i for i, _ in PLUGINS])
def test_param_form_round_trips(app, cls):
    """Defaults, then extreme values, come back out exactly as they went in."""
    from toporia.apps.gui.panels import ParamForm
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
    from toporia.apps.gui import runner
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
    assert "free variables" in stages["Optimiser sees"]      # MMA works on the flat view

    window.core.select_method("q4+pymoto_mma")
    assert dict(window.pipeline.stages())["Updater"] == UPDATERS.get("pymoto_mma").label
    assert window.pipeline.notes() == []          # nothing is lost with this pairing

    window.core.select_method("q4+oc")
    assert any("enforces only the volume budget" in note for note in window.pipeline.notes())
    assert dict(window.pipeline.stages())["Optimiser sees"] == "the design field itself"


def test_older_method_names_select_the_parts_they_stand_for(window):
    window.core.select_method("density_mma")
    assert window.core.method_name() == "q4+mma"
    assert (window.core.model.currentData(), window.core.updater.currentData()) == ("q4", "mma")


@pytest.mark.parametrize("preset", problem_names())
def test_a_preset_survives_the_round_trip_through_the_gui(window, preset):
    from toporia.apps.gui import runner
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
    # Always in view; when the method can add nothing to the volume budget, it says why.
    assert not window.constraints.isHidden()
    assert window.constraints.available() == can_constrain
    assert bool(window.constraints._reason) == (not can_constrain)


def test_a_constraint_reaches_the_run_only_when_the_method_can_enforce_it(window):
    from toporia.apps.gui import runner
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


def test_check_parts_runs_the_conformance_test_on_the_selected_pipeline(window):
    from toporia.apps.gui import runner
    window._on_config_changed("MBB Beam")
    window.core.select_method("q4+oc")
    cfg = runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg,
                              objective=window.objective, constraints=window.constraints)
    lines = []
    assert runner.run_check(cfg, lines.append)
    text = "\n".join(lines)
    for part in ("model:q4", "updater:oc", "representation:element_density", "interpolation:simp",
                 "filter:density", "response:compliance"):
        assert part in text
    assert "6 of 6 parts conform" in text
    assert window.mode.findText("Check Parts") >= 0


def test_compare_methods_lists_every_method_and_runs_the_ticked_ones(window, tmp_path):
    from toporia.apps.gui import runner
    window._on_config_changed("MBB Beam")
    assert window.mode.findText("Compare Methods") >= 0
    assert window.cmg.selected() == ["q4+oc", "q4+mma", "q4+simpl", "q4+beso"]   # the classic four
    assert window.cmg.methods.count() == len(METHOD_NAMES)

    window.cmg.set_selected(["q4+oc", "levelset"])
    cfg = runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg,
                              objective=window.objective, constraints=window.constraints)
    cfg = cfg.updated(m=0.3, max_iter=3, save_every=0).with_output_dir(tmp_path)
    lines = []
    grid = runner.run_compare_methods(cfg, window.cmg, None, lines.append)
    assert grid.exists()
    log = "\n".join(lines)
    assert "referee_compliance" in log and "q4+oc" in log and "levelset" in log
    window.cmg.set_selected(window.cmg.DEFAULT)


def test_the_material_law_panel_follows_the_method(window):
    from toporia.apps.gui import runner
    window._on_config_changed("MBB Beam")
    window.core.select_method("q4+oc")
    assert not window.material.isHidden()
    window.material.load_spec({"type": "ramp", "q": 5.0})
    cfg = runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg,
                              objective=window.objective, constraints=window.constraints,
                              interpolation=window.material)
    assert cfg.solver.interpolation == {"type": "ramp", "q": 5.0}
    offered = [window.sg.param.itemData(i) for i in range(window.sg.param.count())]
    assert "interpolation.q" in offered
    assert dict(window.pipeline.stages())["Material"] == "RAMP (rational)"

    window.core.select_method("pymoto")     # brings its own SIMP inside its network
    assert window.material.isHidden()
    assert dict(window.pipeline.stages())["Material"] == "inside the model"
    window.material.load_spec({"type": "simp"})
    window.core.select_method("q4+oc")


def test_the_design_representation_panel_follows_the_method(window):
    from toporia.apps.gui import runner
    window._on_config_changed("MBB Beam")
    window.core.select_method("q4+mma")
    assert not window.design.representation.isHidden()
    window.design.load_spec({"type": "mmc", "n_x": 3})
    cfg = runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg,
                              objective=window.objective, constraints=window.constraints,
                              interpolation=window.material, representation=window.design)
    assert cfg.solver.representation["type"] == "mmc" and cfg.solver.representation["n_x"] == 3
    offered = [window.sg.param.itemData(i) for i in range(window.sg.param.count())]
    assert "representation.n_x" in offered
    assert dict(window.pipeline.stages())["Design"].startswith("Moving morphable components")

    window.core.select_method("q4+oc")      # cannot move bars: said before the run
    assert any("would be refused" in note for note in window.pipeline.notes())

    window.core.select_method("levelset")   # keeps its own variables
    assert window.design.representation.isHidden() and not window.design.isHidden()
    window.design.load_spec({"type": "element_density"})
    window.core.select_method("q4+oc")


def test_the_design_section_switches_between_2d_and_3d(window):
    window._on_config_changed("Cantilever")
    window.core.select_method("q4+mma")
    assert window.design.get_values() == {"m": pytest.approx(get_run("Cantilever").solver.m), "Lz": 0.0}
    window.design.dims.setCurrentIndex(window.design.dims.findData(3))
    assert window.core.method_name() == "h8+mma"            # the physics follows the dimension
    window.design.depth.setValue(12.0)
    cfg = _built(window)
    assert cfg.scenario.Lz == 12.0 and cfg.solver.method == "h8+mma"
    assert dict(window.pipeline.stages())["Physics"] == "3-D H8 bricks (Toporia)"
    window.lc._rows[0].fe.setValue(30.0)                   # a 3-D load may leave the plane
    assert _built(window).scenario.load_cases[0].Fe == 30.0
    window.design.dims.setCurrentIndex(window.design.dims.findData(2))
    assert window.core.method_name() == "q4+mma" and _built(window).scenario.Lz == 0.0
    assert _built(window).scenario.load_cases[0].Fe == 0.0   # in 2-D a load stays in the plane


def test_the_resolution_can_be_given_as_an_element_size(window):
    window._on_config_changed("Cantilever 3D")
    design = window.design
    assert design.get_values() == {"m": 0.4, "Lz": 10.0}
    assert design.counts.text().startswith("24 × 8 × 4 = 768 elements")
    design.mode.setCurrentIndex(design.mode.findData("size"))
    assert design.resolution.value() == pytest.approx(2.5)          # the same mesh, shown as a size
    design.resolution.setValue(5.0)
    assert design.get_values()["m"] == pytest.approx(0.2)
    assert design.counts.text().startswith("12 × 4 × 2 = 96 elements")
    design.mode.setCurrentIndex(design.mode.findData("per_mm"))
    assert design.resolution.value() == pytest.approx(0.2)


def test_a_3d_run_ends_with_a_3d_view(window, tmp_path):
    pytest.importorskip("skimage")
    from toporia.apps.gui import runner
    window._on_config_changed("Cantilever 3D")
    cfg = _built(window).updated(max_iter=3).with_output_dir(tmp_path)
    density = runner.run_one(cfg, None, lambda *_: None)
    assert density.ndim == 3
    window.canvas.show_3d(density, 1.0 / cfg.solver.m)
    assert window.canvas._ax_d.name == "3d"
    window.canvas.reset()


def _built(window):
    from toporia.apps.gui import runner
    return runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg,
                               objective=window.objective, constraints=window.constraints,
                               interpolation=window.material, representation=window.design,
                               schedules=window.schedules, variants=window.variants, postprocess=window.post,
                               design=window.design)


def test_a_schedule_offers_only_what_can_change_and_reaches_the_run(window):
    window._on_config_changed("MBB Beam")
    window.core.select_method("q4+oc")
    penal = {"path": "interpolation.penal", "type": "steps", "start": 1.0, "end": 3.0, "step": 0.5, "every": 20}
    window.schedules.load_specs([penal])
    assert _built(window).solver.schedules == [penal]
    row = window.schedules._rows[0]
    offered = [row._path.itemData(i) for i in range(row._path.count())]
    assert "interpolation.penal" in offered and "filters[0].rmin" not in offered
    assert dict(window.pipeline.stages())["Schedules"].startswith("interpolation.penal 1 -> 3")
    assert "schedules[0].end" in [window.sg.param.itemData(i) for i in range(window.sg.param.count())]
    window.schedules.load_specs([])


def test_the_robust_button_adds_a_projection_and_three_variants(window):
    window._on_config_changed("MBB Beam")
    window.core.select_method("q4+mma")
    window._use_robust_projection()
    cfg = _built(window)
    assert [spec["type"] for spec in cfg.solver.filter_specs] == ["density", "heaviside"]
    assert cfg.solver.variants["path"] == "filters[1].eta"
    assert cfg.solver.variants["values"] == [0.75, 0.5, 0.25]
    assert "Variants" in dict(window.pipeline.stages())

    window.core.select_method("levelset")   # evaluates itself: no variants, and nothing is lost
    assert window.variants.isHidden() and _built(window).solver.variants == {}
    window.core.select_method("q4+mma")
    cfg = _built(window)
    assert cfg.solver.filter_specs[1]["type"] == "heaviside" and cfg.solver.variants["path"] == "filters[1].eta"
    window.variants.load_spec({})
    window.filters.load_specs([{"type": "density"}])


def test_post_processors_can_be_switched_on_in_any_combination(window):
    window._on_config_changed("MBB Beam")
    assert _built(window).output.postprocess == []           # off unless asked for
    window.post.load_specs([{"type": "threshold"}, {"type": "export_stl", "thickness": 2.0}])
    cfg = _built(window)
    assert [spec["type"] for spec in cfg.output.postprocess] == ["threshold", "export_stl"]
    assert cfg.output.postprocess[1]["thickness"] == 2.0
    assert dict(window.pipeline.stages())["Post-processing"] == "Threshold to black and white -> Export solid (STL)"
    window.core.select_method("levelset")                     # any method's design can be post-processed
    assert not window.post.isHidden() and len(_built(window).output.postprocess) == 2
    window.post.load_specs([])
