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


# ── Help: every option says what it is and where it comes from ────────────────

REGISTRIES = ("methods", "models", "updaters", "filters", "interpolations", "responses",
              "representations", "schedules", "postprocessors")


def _all_plugin_classes():
    import importlib
    for package in REGISTRIES:
        module = importlib.import_module(f"toporia.plugins.{package}")
        yield from getattr(module, package.upper()).classes()


@pytest.mark.parametrize("cls", list(_all_plugin_classes()), ids=lambda c: c.name)
def test_every_plugin_says_where_it_comes_from(cls):
    assert cls.__dict__.get("reference"), f"{cls.__name__} declares no reference"


@pytest.mark.parametrize("preset", problem_names())
def test_every_preset_says_what_it_is_and_where_it_comes_from(preset):
    from toporia.plugins.problems import problem_info
    about, reference = problem_info(preset)
    assert about and reference


def test_every_help_button_in_the_window_opens_a_sourced_topic(window):
    from toporia.apps.gui.help import UNSTATED, HelpButton, HelpWindow
    window._on_config_changed("MBB Beam")
    buttons = window.findChildren(HelpButton)
    assert len(buttons) > 50
    for button in buttons:
        topic = button.topic()
        assert topic.title and topic.section("What it is"), topic
        assert topic.section("Where it is from") not in ("", UNSTATED), topic.title
    buttons[0].open_help()
    help_window = HelpWindow.instance()
    assert help_window.topic is buttons[0].topic() or help_window.topic.title == buttons[0].topic().title
    help_window.close()


@pytest.mark.parametrize("cls", [c for _, c in PLUGINS], ids=[i for i, _ in PLUGINS])
def test_every_generated_parameter_has_a_help_button(app, cls):
    from toporia.apps.gui.help import HelpButton
    from toporia.apps.gui.panels import ParamForm
    form = ParamForm(cls.params, owner=cls)
    buttons = form.findChildren(HelpButton)
    assert len(buttons) == len(cls.params)
    for button, param in zip(buttons, cls.params, strict=True):
        assert button.topic().title.startswith(param.label)


def test_a_dropdowns_help_follows_the_selection(window):
    window._on_config_changed("MBB Beam")
    window.core.select_method("q4+oc")
    row = window.filters._rows[0]
    assert "Bruns" in row.type_topic().section("Where it is from")
    row.load_spec({"type": "heaviside"})
    assert "Guest" in row.type_topic().section("Where it is from")
    window.filters.load_specs([{"type": "density"}])


def test_the_pipeline_is_drawn_as_a_network_whose_boxes_explain_themselves(window):
    from toporia.apps.gui.panels.pipeline import node_topic
    window._on_config_changed("MBB Beam")
    window.core.select_method("q4+mma")
    window._use_robust_projection()
    window.schedules.load_specs([{"path": "interpolation.penal", "type": "steps", "start": 1.0, "end": 3.0,
                                  "step": 0.5, "every": 20}])
    nodes = window.pipeline.graph.nodes()
    titles = [n.title for n in nodes]
    assert titles == ["Design", "Filter 1", "Filter 2", "Material law", "Physics", "Objective", "Constraint",
                      "Updater"]
    by_title = {n.title: n for n in nodes}
    assert by_title["Filter 2"].badges == ["⧉ eta = 0.75, 0.5, 0.25"]
    assert by_title["Material law"].badges == ["↻ penal 1 → 3"]
    for node in nodes:
        assert node_topic(node).section("Where it is from")
    assert "Guest" in node_topic(by_title["Filter 2"]).section("Where it is from")

    window.post.load_specs([{"type": "threshold"}])
    assert [n.label for n in window.pipeline.graph.nodes()][-1] == "Threshold to black and white"
    window.core.select_method("levelset")
    assert window.pipeline.graph.nodes()[0].title == "Whole method"
    window.post.load_specs([])
    window.schedules.load_specs([])
    window.variants.load_spec({})
    window.filters.load_specs([{"type": "density"}])
    window.core.select_method("q4+oc")


# ── Problem preview: the problem is shown before it is solved ─────────────────


@pytest.mark.parametrize("preset", problem_names())
def test_every_preset_can_be_drawn_before_it_is_solved(preset):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from toporia.apps.gui.preview import describe_problem, draw_problem
    run = get_run(preset)
    fig, ax = plt.subplots()
    shown = draw_problem(ax, run.scenario, title=describe_problem(run.scenario, run.solver.m, preset))
    plt.close(fig)
    assert "Support" in shown and any(label.startswith("Load") for label in shown)


def test_the_fallback_supports_and_loads_are_drawn_where_the_solver_puts_them():
    from toporia.apps.gui.preview import supports_and_loads
    from toporia.framework import Scenario
    edges, points, loads = supports_and_loads(Scenario(Lx=80.0, Ly=40.0))
    assert edges == [("left", "both")] and points == [] and loads == [(80.0, 20.0)]


def test_the_view_shows_the_problem_until_a_run_starts(window):
    window.config_combo.setCurrentText("Cantilever")
    window.go_to_step(0)
    window.show_problem()
    assert window.canvas.showing_problem
    assert "Cantilever:" in window.canvas._ax_d.get_title()
    window.canvas.reset()                       # what a run does first
    assert not window.canvas.showing_problem
    window._running = True
    window.show_problem()                       # a running optimisation keeps the view
    assert not window.canvas.showing_problem
    window._running = False
    window.config_combo.setCurrentText("MBB Beam")


def test_post_processors_can_be_applied_to_the_last_design_without_a_new_run(window, tmp_path):
    from toporia.apps.gui import runner
    window.config_combo.setCurrentText("MBB Beam")
    cfg = _built(window).updated(max_iter=3, m=0.3, save_every=0).with_output_dir(tmp_path)
    runner.run_one(cfg, None, lambda *_: None)
    window._refresh_export_buttons()
    assert window.export_btn.isEnabled()

    window.post.load_specs([{"type": "threshold"}, {"type": "export_svg"}])
    lines = []
    window._log = lines.append
    window._on_export()
    del window._log
    assert any("2 of 2 post-processors" in line for line in lines), lines
    assert list((runner.last_run_folder / "post").glob("*.svg"))
    window.post.load_specs([])


def test_sweep_methods_puts_the_methods_down_the_rows_and_a_setting_across(window, tmp_path):
    import csv

    from toporia.apps.gui import runner
    window.config_combo.setCurrentText("MBB Beam")
    window.mode.setCurrentText("Sweep Methods")
    assert not window.msg.isHidden() and window.run_btn.text() == "▶  Run: Sweep Methods"
    window.msg.set_selected(["q4+oc", "q4+mma"])
    window.msg.param.setCurrentIndex(window.msg.param.findData("volfrac"))
    window.msg.min_val.setValue(0.3)
    window.msg.max_val.setValue(0.5)
    window.msg.n_values.setValue(2)
    cfg = _built(window).updated(m=0.3, max_iter=2, save_every=0).with_output_dir(tmp_path)
    grid = runner.run_sweep_methods(cfg, window.msg, None, lambda *_: None)
    assert grid.exists()
    with open(grid.parent / "methods_sweep.csv", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert [(r["method"], float(r["volfrac"])) for r in rows] == [
        ("q4+oc", 0.3), ("q4+oc", 0.5), ("q4+mma", 0.3), ("q4+mma", 0.5)]
    assert all(r["status"] == "ran" for r in rows)
    window.msg.set_selected(window.msg.DEFAULT)
    window.mode.setCurrentText("Run One")


# ── Every part can be picked: nothing registered is out of reach of the GUI ────────────────

def _menu_texts(window):
    """Every entry of every drop-down and list in the window."""
    texts = set()
    for combo in window.findChildren(QtWidgets.QComboBox):
        texts.update(combo.itemText(i).strip() for i in range(combo.count()))
    for widget in window.findChildren(QtWidgets.QListWidget):
        texts.update(widget.item(i).text().strip() for i in range(widget.count()))
    return "\n".join(texts)


def test_every_registered_part_and_preset_can_be_picked_in_the_gui(window):
    import importlib
    window.post._add_row()                          # the post-processor and schedule lists build
    window._on_config_changed("MBB Beam (Robust)")  # their drop-downs per row; a robust preset
    window.schedules._add_row()                     # has schedulable paths, so a row can be added
    window._on_config_changed("L-bracket (local stress)")   # a method that takes constraints: the
    window.constraints._add_row()                   # constraint rows then offer every constraint
    texts = _menu_texts(window)
    # A drop-down offers what the selected method can do (a heat model offers thermal compliance,
    # a structural one does not), so a part is reachable when some preset's menus show it.
    for name in problem_names():
        window._on_config_changed(name)
        texts += "\n" + _menu_texts(window)

    # The objectives and constraints offered follow from the model, so a part that only some models
    # compute (the vibration responses) shows up when a preset that uses such a model is loaded.
    for preset in ("Vibrating Beam",):
        window._on_config_changed(preset)
        window.core.select_method("q4_dynamic+mmapy_mma")                   # one that can enforce a constraint
        window.constraints.load_specs([{"type": "eigenfrequency_limit"}])   # a row builds its drop-down
        texts += _menu_texts(window)
        window.constraints.load_specs([])
    missing = [f"{package}:{cls.name}"
               for package in REGISTRIES
               for cls in getattr(importlib.import_module(f"toporia.plugins.{package}"),
                                  package.upper()).classes()
               if (cls.label or cls.name) not in texts and cls.name not in texts]
    missing += [f"problem:{name}" for name in problem_names() if name not in texts]
    assert not missing, f"not reachable from the GUI: {missing}"


def test_the_heat_sink_preset_offers_thermal_compliance_and_runs_from_the_gui(window):
    from toporia.apps.gui import runner
    from toporia.engine.loop import initialized_method
    window._on_config_changed("Heat Sink")
    assert window.core.method_name() == "q4_heat+oc"
    assert window.objective.offered_types() == ["thermal_compliance"]
    run = runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg)
    assert run.scenario.objective["type"] == "thermal_compliance"
    method = initialized_method(run.updated(max_iter=3, tol=0.0, save_every=0))
    for iteration in (1, 2, 3):
        method.step(iteration)
    assert method.get_responses()["objective"] > 0
    # Choosing the model alone offers it too, and the structural objectives disappear.
    window.core.select_method("q4_heat+mma")
    assert "thermal_compliance" in window.objective.offered_types() and "compliance" not in window.objective.offered_types()


def test_the_force_inverter_preserves_springs_and_its_signed_output_in_the_gui(window):
    from toporia.apps.gui import runner
    from toporia.checks.common import iterate
    from toporia.engine.loop import initialized_method
    window._on_config_changed("Force Inverter")
    assert window.core.method_name() == "q4_mechanism+mma"
    assert "output_displacement" in window.objective.offered_types()
    run = runner.build_config(window.core, window.lc, window.filters, base_cfg=window._base_cfg,
                              objective=window.objective)
    assert run.scenario.point_springs == get_run("Force Inverter").scenario.point_springs
    assert run.scenario.objective == get_run("Force Inverter").scenario.objective
    assert run.scenario.load_cases == get_run("Force Inverter").scenario.load_cases
    method = initialized_method(run.updated(m=0.4, save_every=0))
    try:
        iterate(method, 200, tol=0.001)
        final = method._model.evaluate(method.x, gradients=False)
        assert final.reported["output_displacement"] > 0.001
        assert method.get_density().mean() <= 0.4001
    finally:
        method.close()


@pytest.mark.parametrize("magnitude", [0.000001, 0.001, 0.012345, 1.0, 1234.56789])
def test_load_case_rows_preserve_small_force_magnitudes(app, magnitude):
    from toporia.apps.gui.panels.loads import LoadCaseRow

    row = LoadCaseRow(1, fmag=magnitude)
    assert row.get().Fmag == pytest.approx(magnitude, rel=1e-12)
