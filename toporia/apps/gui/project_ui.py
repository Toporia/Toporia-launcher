# apps/gui/project_ui.py — file actions and project lifecycle for MainWindow.
# Keeps persistence, prompts and notes out of the optimisation/preview wiring.

from dataclasses import asdict, replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QMessageBox,
    QSpinBox,
    QTextEdit,
)

from toporia.framework.problem.run import Run
from toporia.framework.problem.scenario import Scenario

from .project import ProblemDocument, Project

STUDY_GROUPS = ("sg", "sg2", "cg", "clcg", "cmg", "msg", "sens", "ssg", "ssg2")


class ProjectActions:
    """A MainWindow mixin for a single portable project and its unsaved changes."""

    def _setup_project_ui(self):
        """Add file commands and a notes panel after the window's controls exist."""
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Project notes, observations and references…")
        self.notes_dock = QDockWidget("Project notes", self)
        self.notes_dock.setWidget(self.notes)
        self.addDockWidget(Qt.RightDockWidgetArea, self.notes_dock)
        self.notes_dock.hide()
        menu = self.menuBar().addMenu("File")
        self.file_actions = []
        for title, shortcut, callback in (
            ("Home / benchmark library", "Ctrl+H", self.show_home),
            ("New blank problem", QKeySequence.New, self.new_blank),
            ("Open project…", QKeySequence.Open, self.open_project),
            ("Save project", QKeySequence.Save, self.save_project),
            ("Save project as…", QKeySequence.SaveAs, lambda: self.save_project(save_as=True)),
            ("Import problem…", "Ctrl+I", self.import_problem),
            ("Export problem…", "Ctrl+E", self.export_problem),
            ("Copy benchmark to custom problem", "", self.copy_to_custom),
        ):
            action = QAction(title, self)
            if shortcut:
                action.setShortcut(shortcut)
            action.triggered.connect(lambda _=False, fn=callback: fn())
            menu.addAction(action)
            self.file_actions.append(action)
        view = self.menuBar().addMenu("View")
        view.addAction(self.notes_dock.toggleViewAction())
        from .appearance import add_appearance_menu
        add_appearance_menu(self, view)
        self.home.open_requested.connect(self.open_project)
        self.home.blank_requested.connect(self.new_blank)
        self.home.import_requested.connect(self.import_problem)
        self.home.benchmark_requested.connect(self.open_benchmark)
        self._saved_state = self._capture_project().payload()
        self._clean_geometry = self.project.objects
        self._dirty_timer = QTimer(self)
        self._dirty_timer.setInterval(800)
        self._dirty_timer.timeout.connect(self._update_project_title)
        self._dirty_timer.start()

    def current_config(self):
        """Read the complete Run while preserving non-widget scenario fields."""
        from .config import build_config
        cfg = build_config(self.core, self.lc, self.filters, base_cfg=self._base_cfg,
                            objective=self.objective, constraints=self.constraints,
                            interpolation=self.material, representation=self.design,
                            schedules=self.schedules, variants=self.variants,
                            postprocess=self.post, design=self.design)
        if self.project.objects is not None:
            cfg = replace(cfg, scenario=replace(cfg.scenario, regions=self.project.objects))
        elif self.project.benchmark is not None:
            cfg = replace(cfg, scenario=self.project.run.scenario)
        return cfg

    def _capture_study(self):
        """Remember numeric, parameter and method selections for every study mode."""
        data = {"mode": self.mode.currentText()}
        for name in STUDY_GROUPS:
            group = getattr(self, name)
            values = {}
            for key, widget in vars(group).items():
                if isinstance(widget, QComboBox):
                    values[key] = widget.currentData() if widget.currentData() is not None else widget.currentText()
                elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                    values[key] = widget.value()
            if hasattr(group, "selected"):
                values["selected"] = group.selected()
            for key in ("lc_a", "lc_b"):
                if hasattr(group, key):
                    values[key] = [asdict(case) for case in getattr(group, key).get_load_cases()]
            data[name] = values
        return data

    def _restore_study(self, data):
        """Restore study values only after plugin parameter paths have been rebuilt."""
        from toporia.framework.problem.scenario import LoadCase
        self.mode.setCurrentText(data.get("mode", "Run One"))
        for name in STUDY_GROUPS:
            group = getattr(self, name)
            for key, value in data.get(name, {}).items():
                widget = getattr(group, key, None)
                if key == "selected" and hasattr(group, "set_selected"):
                    group.set_selected(value)
                elif isinstance(widget, QComboBox):
                    index = widget.findData(value)
                    widget.setCurrentIndex(index if index >= 0 else widget.findText(str(value)))
                elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                    widget.setValue(value)
                elif key in ("lc_a", "lc_b"):
                    cfg = self._base_cfg.updated(load_cases=[LoadCase(**v) for v in value])
                    widget.load_from_config(cfg)

    def _capture_project(self):
        """Snapshot editable inputs; result arrays never enter the project document."""
        self._store_active_stage()
        return replace(self.project, run=self.current_config(), notes=self.notes.toPlainText() if hasattr(self, "notes") else "",
                       study=self._capture_study())

    def _is_dirty(self):
        """Compare actual controls rather than relying on incomplete signal wiring."""
        # Do not copy embedded STL triangles at every title-bar timer tick.
        # Editor operations replace the object list, so identity caches equality.
        objects = self.project.objects
        if objects is not getattr(self, "_compared_geometry", None):
            self._compared_geometry = objects
            self._geometry_dirty = objects != self._saved_state.get("objects")
        geometry_dirty = False if objects is getattr(self, "_clean_geometry", None) else getattr(self, "_geometry_dirty", False)
        saved = {**self._saved_state, "objects": None, "scenario": dict(self._saved_state["scenario"])}
        saved["scenario"].pop("regions", None)
        return geometry_dirty or self._capture_project().payload(include_geometry=False) != saved

    def _update_project_title(self):
        """Show the active project and a standard unsaved-change marker."""
        if self._running:
            return
        from . import GUI_VERSION
        self.setWindowTitle(f"{self.project.name}[*] — Toporia GUI {GUI_VERSION}")
        self.setWindowModified(self._is_dirty())

    def _maybe_discard(self):
        """Offer Save / Discard / Cancel before replacing a changed configuration."""
        if self._running:
            return False
        if not self._is_dirty():
            return True
        choice = QMessageBox.question(self, "Unsaved project", "Save changes before continuing?",
                                      QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if choice == QMessageBox.Save:
            return self.save_project()
        return choice == QMessageBox.Discard

    def _populate_run(self, cfg):
        """Load a Run into the existing generated forms without inventing a preset."""
        self._base_cfg = cfg
        self.core.load_from_config(cfg)
        self.design.load_from_config(cfg)
        self.material.load_spec(cfg.solver.interpolation)
        self.objective.load_spec(cfg.scenario.objective)
        self.constraints.load_specs(cfg.scenario.constraints)
        self.filters.load_specs(cfg.solver.filter_specs)
        self.schedules.load_specs(cfg.solver.schedules)
        self.variants.load_spec(cfg.solver.variants)
        self.post.load_specs(cfg.output.postprocess)
        self.lc.load_from_config(cfg)
        self.lc.set_regional(self.project.objects is not None)
        self._on_method_changed(self.core.method_name())

    def _activate_project(self, project):
        """Replace the document and reset result ownership when changing projects."""
        from . import runner
        runner.last_run_folder = None
        self._result_density = None
        self._result_config = None
        self._result_objectives = []
        self._result_iteration = 0
        self.project = project
        self._active_stage = project.view.get("active_stage")
        self.display_options.load(project.view.get("display", {}))
        self._set_display_options(self.display_options.values())
        self._restore_inspector()
        self.problem_editor.spatial.restore_camera(project.view.get("camera3d"))
        if project.objects is not None:
            project.run = replace(project.run, scenario=replace(project.run.scenario, regions=project.objects))
        elif project.run.scenario.regions is not None:
            project.objects = project.run.scenario.regions
        self.method_view.positions = project.view.get("method_positions", {})
        self.method_view._signature = None
        tree = self._ensure_workflow()
        from toporia.framework.problem.workflow import nodes, stage_run
        stage = next(node for node in nodes(tree) if node["id"] == self._active_stage)
        self.method_view.context = "root"
        self._loading_stage = True
        try:
            self._populate_run(stage_run(project.run, stage))
        finally:
            self._loading_stage = False
        self._refresh_pipeline()
        if hasattr(self, "notes"):
            self.notes.setPlainText(project.notes)
        self._restore_study(project.study)
        self._apply_problem_lock()
        self._refresh_export_buttons()
        self.canvas.reset()
        self.post_canvas.reset()
        self._refresh_run_history()
        self._saved_state = self._capture_project().payload()
        self._clean_geometry = self.project.objects
        self.root_pages.setCurrentIndex(1)
        self.go_to_step(0)
        self._show_blank_setup()
        self._update_project_title()

    def _blank_pending(self):
        """Only new custom drafts use onboarding; existing documents open directly."""
        return hasattr(self, "project") and "blank_setup" in self.project.view

    def _remember_blank_setup(self, state):
        if self._blank_pending() and not getattr(self, "_loading_blank", False):
            self.project.view["blank_setup"] = state

    def _show_blank_setup(self):
        pending = self._blank_pending()
        self.sidebar.setVisible(not pending)
        for index, button in enumerate(self._step_buttons.buttons()):
            button.setEnabled(not pending or index == 0)
        self._show_run_label()
        if pending:
            self._loading_blank = True
            try:
                self.blank_setup.load(self.project.view["blank_setup"])
            finally:
                self._loading_blank = False
            self.workspace_views.setCurrentWidget(self.blank_setup)

    def _complete_blank_setup(self, state):
        """Create the physical definition only after every initial choice is explicit."""
        if not self._blank_pending() or not self.blank_setup.create.isEnabled():
            return
        from toporia.framework.problem.solver import Solver
        scenario = Scenario(Lx=state["Lx"], Ly=state["Ly"], Lz=state["Lz"] if state["dimension"] == 3 else 0,
                            E0=state["E0"], nu=state["nu"], volfrac=state["volfrac"],
                            objective={"type": state["objective"]}, regions=[])
        solver = Solver(method=self.blank_setup.method_name(), m=1 / state["element_size"],
                        representation={"type": state["representation"]},
                        method_params={"move": .02} if state["representation"] == "mmc" else {})
        saved = self._saved_state
        view = {k: v for k, v in self.project.view.items() if k != "blank_setup"}
        project = replace(self._capture_project(), run=Run(scenario=scenario, solver=solver), objects=[], view=view)
        # Completing onboarding replaces provisional computational defaults with
        # the explicitly chosen settings. Preserve the workflow and its identity.
        tree = project.workflow
        if tree is not None and tree["kind"] == "optimization":
            from toporia.framework.problem.workflow import stage_settings
            tree["settings"] = stage_settings(project.run)
        self._activate_project(project)
        self._saved_state = saved  # Creating a domain is an unsaved physical edit.
        self._update_project_title()
        self.statusBar().showMessage("Design space created. Add supports and loads, then review Method.", 10000)

    def _apply_problem_lock(self):
        """Protect reference problems while allowing solver and resolution experiments."""
        locked = self.project.benchmark is not None
        self.lc.set_regional(self.project.objects is not None)
        for widget in (self.core.volume_box, self.lc, self.objective, self.constraints,
                       self.design.dims, self.design.depth):
            widget.setEnabled(not locked)
        if hasattr(self, "project_label"):
            self.project_label.setText(self.project.name + (" · benchmark" if locked else " · custom"))

    def show_home(self):
        """Keep the current project in memory while browsing the library."""
        if not self._running:
            self.home.open_section(0)
            self.root_pages.setCurrentIndex(0)
            self.navigation_bar.hide()

    def open_benchmark(self, name):
        """Open an immutable reference; existing custom work gets a save prompt."""
        from toporia.plugins.problems import get_run
        if self._maybe_discard():
            self._activate_project(Project(name, get_run(name), benchmark=name))

    def new_blank(self):
        """Start an explicit empty scene rather than the solver's legacy cantilever fallback."""
        if self._maybe_discard():
            self._activate_project(Project("Untitled", Run(scenario=Scenario(regions=[])), objects=[],
                                           view={"blank_setup": {}}))

    def copy_to_custom(self):
        """Detach the physical definition from its reference without losing method settings."""
        if not self._running and not self._blank_pending():
            self.project = replace(self._capture_project(), name=self.project.name + " copy", benchmark=None, path=None)
            if self.project.objects is None:
                from .geometry import objects_from_scenario
                self.project.objects = objects_from_scenario(self.project.run.scenario)
            self._base_cfg = replace(self._base_cfg, scenario=replace(self._base_cfg.scenario, regions=self.project.objects))
            self._apply_problem_lock()
            self.show_problem()
            self._update_project_title()

    def open_project(self, path=None):
        """Read first so a malformed file cannot replace a working project."""
        if not self._maybe_discard():
            return False
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Open Toporia project", "", "Toporia project (*.top);;JSON (*.json)")
        if not path:
            return False
        try:
            project = Project.load(path)
            from toporia.engine.pipeline import pipeline_parts
            pipeline_parts(project.run)  # Resolve every named plugin before replacing the working document.
            if project.workflow is not None:
                from toporia.framework.problem.workflow import nodes, stage_run
                for node in nodes(project.workflow):
                    if node["kind"] == "optimization":
                        pipeline_parts(stage_run(project.run, node))
            self._activate_project(project)
        except (OSError, ValueError, KeyError, TypeError) as error:
            QMessageBox.warning(self, "Cannot open project", str(error))
            return False
        return True

    def save_project(self, path=None, save_as=False):
        """Save all controls and notes, then establish the new clean checkpoint."""
        project = self._capture_project()
        if path is None and (project.path is None or save_as):
            path, _ = QFileDialog.getSaveFileName(self, "Save Toporia project", f"{project.name}/project.top",
                                                 "Toporia project (*.top)")
            if not path:
                return False
        try:
            project.save(path)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.warning(self, "Cannot save project", str(error))
            return False
        self.project = project
        self._saved_state = project.payload()
        self._clean_geometry = self.project.objects
        self._update_project_title()
        self.statusBar().showMessage(f"Saved {project.path}", 6000)
        return True

    def import_problem(self, path=None):
        """Import an independent physical definition with default method settings."""
        if not self._maybe_discard():
            return False
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Import problem", "", "Toporia problem (*.pro *.json)")
        if not path:
            return False
        try:
            problem = ProblemDocument.load(path)
            self._activate_project(Project(Path(path).stem, Run(scenario=problem.scenario), objects=problem.objects))
        except (OSError, ValueError, KeyError, TypeError) as error:
            QMessageBox.warning(self, "Cannot import problem", str(error))
            return False
        return True

    def export_problem(self, path=None):
        """Export only the physical definition, excluding the method and results."""
        if self._blank_pending():
            QMessageBox.information(self, "Finish problem setup", "Create the design space before exporting a problem. You can save the unfinished project instead.")
            return False
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Export problem", f"{self.project.name}.pro", "Toporia problem (*.pro)")
        if not path:
            return False
        try:
            self._capture_project().problem.save(path)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.warning(self, "Cannot export problem", str(error))
            return False
        return True

    def closeEvent(self, event):
        """Prevent closing an active run or losing unsaved configuration changes."""
        if self._maybe_discard():
            self.problem_editor.spatial.shutdown()
            event.accept()
        else:
            event.ignore()
