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
        self.home.open_requested.connect(self.open_project)
        self.home.blank_requested.connect(self.new_blank)
        self.home.import_requested.connect(self.import_problem)
        self.home.benchmark_requested.connect(self.open_benchmark)
        self._saved_state = self._capture_project().payload()
        self._dirty_timer = QTimer(self)
        self._dirty_timer.setInterval(800)
        self._dirty_timer.timeout.connect(self._update_project_title)
        self._dirty_timer.start()

    def current_config(self):
        """Read the complete Run while preserving non-widget scenario fields."""
        from .config import build_config
        return build_config(self.core, self.lc, self.filters, base_cfg=self._base_cfg,
                            objective=self.objective, constraints=self.constraints,
                            interpolation=self.material, representation=self.design,
                            schedules=self.schedules, variants=self.variants,
                            postprocess=self.post, design=self.design)

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
        return replace(self.project, run=self.current_config(), notes=self.notes.toPlainText() if hasattr(self, "notes") else "",
                       study=self._capture_study())

    def _is_dirty(self):
        """Compare actual controls rather than relying on incomplete signal wiring."""
        return self._capture_project().payload() != self._saved_state

    def _update_project_title(self):
        """Show the active project and a standard unsaved-change marker."""
        if self._running:
            return
        self.setWindowTitle(f"{self.project.name}[*] — Toporia")
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
        self._on_method_changed(self.core.method_name())

    def _activate_project(self, project):
        """Replace the document and reset result ownership when changing projects."""
        from . import runner
        runner.last_run_folder = None
        self.project = project
        self._populate_run(project.run)
        if hasattr(self, "notes"):
            self.notes.setPlainText(project.notes)
        self._restore_study(project.study)
        self._apply_problem_lock()
        self._refresh_export_buttons()
        self._saved_state = self._capture_project().payload()
        self.root_pages.setCurrentIndex(1)
        self.go_to_step(0)
        self._update_project_title()

    def _apply_problem_lock(self):
        """Protect reference problems while allowing solver and resolution experiments."""
        locked = self.project.benchmark is not None
        for widget in (self.core.volume_box, self.lc, self.objective, self.constraints,
                       self.design.dims, self.design.depth):
            widget.setEnabled(not locked)
        if hasattr(self, "project_label"):
            self.project_label.setText(self.project.name + (" · benchmark" if locked else " · custom"))

    def show_home(self):
        """Keep the current project in memory while browsing the library."""
        if not self._running:
            self.root_pages.setCurrentIndex(0)

    def open_benchmark(self, name):
        """Open an immutable reference; existing custom work gets a save prompt."""
        from toporia.plugins.problems import get_run
        if self._maybe_discard():
            self._activate_project(Project(name, get_run(name), benchmark=name))

    def new_blank(self):
        """Start an explicit empty scene rather than the solver's legacy cantilever fallback."""
        if self._maybe_discard():
            self._activate_project(Project("Untitled", Run(scenario=Scenario(load_cases=[])), objects=[]))

    def copy_to_custom(self):
        """Detach the physical definition from its reference without losing method settings."""
        if not self._running:
            self.project = replace(self._capture_project(), name=self.project.name + " copy", benchmark=None, path=None)
            self._apply_problem_lock()
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
            event.accept()
        else:
            event.ignore()
