# apps/gui/window.py — the main application window
#
# Home opens portable projects and the benchmark library. The persistent steps
# switch both the left settings and the main workspace: physical editor, method
# diagram, asynchronous runner, then post-processing. Numerical execution lives
# in gui_worker.py, with the Qt lifecycle in execution.py. Plugin declarations
# still generate controls; project_ui.py owns file actions and dirty tracking.

import traceback  # for formatting Python exception messages into readable text

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .blank_setup import BlankSetup
from .canvas import LiveCanvas
from .editor import ProblemEditor
from .execution import ExecutionActions
from .help import text_topic, with_help
from .home import HomePage
from .method_view import MethodWorkspace
from .panels import (
    CompareLoadCasesParamsGroup,
    CompareMethodsParamsGroup,
    CompareTwoParamsGroup,
    ConstraintsGroup,
    CoreParamsGroup,
    DesignSection,
    LoadCasesGroup,
    MaterialGroup,
    MethodsSweepParamsGroup,
    ObjectiveGroup,
    PipelineView,
    ScheduleListGroup,
    SensitivityParamsGroup,
    SensitivitySweep2DParamsGroup,
    SensitivitySweepParamsGroup,
    SpecListGroup,
    Sweep2DParamsGroup,
    SweepParamsGroup,
    VariantsGroup,
)
from .project import Project
from .project_ui import ProjectActions
from .workflow_ui import WorkflowActions

#: The steps along the top, in the order one walks through them before a run.
STEPS = (
    ("Problem", "What is designed: the design space, the material budget, the loads and supports, "
                "what is optimised and what must hold."),
    ("Method", "How it is optimised: the physics, the updater, the material law, the filters "
               "and anything that changes during the run."),
    ("Runner", "What kind of run: one design, a sweep, a comparison, a sensitivity study, "
              "or a check of every part."),
    ("Post-process", "Modify the finished design and inspect the updated result."),
    ("Export", "Write the current result to files outside the project."),
)

#: Every kind of run, with what it does and where it comes from, for the Mode "?".
MODES = {
    "Run One": ("One optimisation of the problem as set up in the steps before.",
                "Toporia's own."),
    "Sweep": ("One setting stepped through a range of values, one design per value, shown as a grid.",
              "Toporia's own parameter study."),
    "Sweep 2D": ("Two settings stepped together, one along the rows and one along the columns.",
                 "Toporia's own parameter study."),
    "Compare Two": ("Two designs side by side, differing in one setting.",
                    "Toporia's own."),
    "Compare Load Cases": ("Two designs side by side, each optimised for its own set of load cases.",
                           "Toporia's own."),
    "Compare Methods": ("The ticked methods on the same problem, mesh, filters and stopping rule, with one "
                        "image of the designs and one table of results, each design re-analysed the same way.",
                        "Method comparisons on common benchmarks, e.g. S. Rojas-Labanda, M. Stolpe, "
                        '"Benchmarking optimization solvers for structural topology optimization", '
                        "Struct. Multidisc. Optim. 52 (2015) 527-547."),
    "Sweep Methods": ("The ticked methods down the rows and one setting swept across the columns: how each "
                      "optimiser reacts to the same change, every cell a whole run on the same problem.",
                      "Toporia's own; method comparisons over a parameter range are common in the "
                      "literature, e.g. Rojas-Labanda & Stolpe, Struct. Multidisc. Optim. 52 (2015) 527-547."),
    "Sensitivity": ("Two optimisations, at a setting's base value and at base + gap; the change of each "
                    "element's density divided by the gap, drawn blue to red.",
                    "Toporia's own: a finite-difference sensitivity of the final design to a setting."),
    "Sensitivity Sweep": ("The sensitivity above, repeated over a sweep of a second setting.",
                          "Toporia's own."),
    "Sensitivity Sweep 2D": ("The sensitivity above, repeated over a two-setting sweep.",
                             "Toporia's own."),
    "Check Parts": ("The conformance test on every part of the selected pipeline: its interface, its "
                    "gradients against finite differences, and a small benchmark.",
                    "Toporia's own (toporia.checks); gradient checks by finite differences are standard "
                    "practice for adjoint sensitivities."),
}


class MainWindow(WorkflowActions, ProjectActions, ExecutionActions, QMainWindow):
    """A project desktop with separate physical, method, run and export workspaces."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Toporia — Topology Optimisation")
        self.resize(1440, 860)
        self._base_cfg = None  # set by _on_config_changed; holds geometry from selected config
        self._stop = False     # flag checked inside on_iter to interrupt the loop
        self._running = False  # while a run draws on the canvas, the problem preview stays away
        self._result_density = None
        self._result_config = None
        self._result_objectives = []
        self._result_iteration = 0
        self._pending_iteration = None
        self._display_timer = QTimer(self)
        self._display_timer.setInterval(33)
        self._display_timer.setSingleShot(True)
        self._display_timer.timeout.connect(self._draw_pending_iteration)
        self._preview_timer = QTimer(self)   # edits come in bursts: redraw once they settle
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self.show_problem)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._build_panels()
        outer.addWidget(self._build_top_bar())

        # Sidebar | view + log | pipeline — every divider can be dragged.
        body = QSplitter(Qt.Horizontal)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_view())
        body.setStretchFactor(1, 1)
        body.setSizes([350, 1090])
        self.workspace = body
        self.root_pages = QStackedWidget()
        self.home = HomePage()
        self.root_pages.addWidget(self.home)
        self.root_pages.addWidget(body)
        outer.addWidget(self.root_pages, 1)

        self._wire_panels()

        # Wire the configuration dropdown now that self.log exists so error messages work.
        self.config_combo.currentTextChanged.connect(self._on_config_changed)
        self._on_config_changed(self.config_combo.currentText())  # populate widgets from first config

        self._on_mode("Run One")  # hide sweep-specific groups on startup
        self.go_to_step(0)
        self._report_plugin_errors()
        self._setup_project_ui()
        self.show_home()
        self.refresh_appearance()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_panels(self):
        """Create every settings panel; where each one sits is decided by _build_sidebar."""
        from toporia.plugins.filters import FILTERS
        from toporia.plugins.interpolations import INTERPOLATIONS
        from toporia.plugins.postprocessors import POSTPROCESSORS
        from toporia.plugins.representations import REPRESENTATIONS
        from toporia.plugins.responses import CONSTRAINT_ROLE, OBJECTIVE_ROLE, responses_for
        from toporia.plugins.schedules import SCHEDULES

        self.pipeline = PipelineView()  # what the run is made of, kept in view on the right
        self.core = CoreParamsGroup()
        self.design = DesignSection(REPRESENTATIONS.classes())
        self.material = MaterialGroup(INTERPOLATIONS.classes())
        self.objective = ObjectiveGroup(responses_for(OBJECTIVE_ROLE))
        self.constraints = ConstraintsGroup(responses_for(CONSTRAINT_ROLE))
        self.filters = SpecListGroup("Filters", FILTERS.classes(), initial=[{"type": "density"}], noun="filter")
        self.schedules = ScheduleListGroup(SCHEDULES.classes())
        self.variants = VariantsGroup()
        self.post = SpecListGroup("Post-processing", POSTPROCESSORS.classes(), noun="post-processor")
        self.lc = LoadCasesGroup()
        self.sg = SweepParamsGroup()
        self.sg2 = Sweep2DParamsGroup()
        self.cg = CompareTwoParamsGroup()
        self.clcg = CompareLoadCasesParamsGroup()
        self.cmg = CompareMethodsParamsGroup()
        self.msg = MethodsSweepParamsGroup()
        self.sens = SensitivityParamsGroup()
        self.ssg = SensitivitySweepParamsGroup()
        self.ssg2 = SensitivitySweep2DParamsGroup()

        self.mode = QComboBox()
        self.mode.addItems(MODES)
        self.mode.currentTextChanged.connect(self._on_mode)  # call _on_mode when selection changes

    def _build_top_bar(self):
        """Preset, the numbered steps, and Run — the slicer's top row."""
        from toporia.plugins.problems import DEFAULT_PROBLEM, problem_names

        bar = QFrame()
        self.navigation_bar = bar
        bar.setObjectName("topBar")
        bar.setStyleSheet(
            "#topBar { border-bottom: 1px solid palette(mid); }"
            "QToolButton[step=true] { padding: 6px 14px; border: none; border-bottom: 3px solid transparent; }"
            "QToolButton[step=true]:checked { border-bottom: 3px solid palette(highlight); font-weight: bold; }"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 6, 10, 6)

        title = QLabel("<b>Toporia</b>")
        f = title.font()
        f.setPointSize(13)
        title.setFont(f)
        row.addWidget(title)
        row.addSpacing(16)

        home_button = QPushButton("Home")
        home_button.clicked.connect(self.show_home)
        row.addWidget(home_button)
        self.project_label = QLabel()
        row.addWidget(self.project_label)
        self.config_combo = QComboBox()
        self.config_combo.addItems(problem_names())
        self.config_combo.setCurrentText(DEFAULT_PROBLEM)
        self.config_combo.setToolTip("A ready-made problem: loads every step below with its settings.")
        # Kept as the preset-loading adapter for callers; the library is the visible selector.
        self.config_combo.setParent(bar)
        self.config_combo.hide()
        row.addSpacing(24)

        self._step_buttons = QButtonGroup(self)
        self._step_buttons.setExclusive(True)
        for index, (name, about) in enumerate(STEPS):
            if index:
                row.addWidget(QLabel("›"))
            button = QToolButton()
            button.setText(f"{index + 1}  {name}".replace("&", "&&"))   # a single & would mark a shortcut
            button.setToolTip(about)
            button.setCheckable(True)
            button.setProperty("step", True)
            self._step_buttons.addButton(button, index)
            row.addWidget(button)
        self._step_buttons.idClicked.connect(self.go_to_step)
        row.addStretch(1)

        self.run_btn = QPushButton()
        self.run_btn.setFixedHeight(36)
        self.run_btn.setMinimumWidth(170)
        f = self.run_btn.font()
        f.setPointSize(11)
        f.setBold(True)
        self.run_btn.setFont(f)
        self.run_btn.clicked.connect(self._on_run)
        row.addWidget(self.run_btn)
        self._show_run_label()
        return bar

    def _build_sidebar(self):
        """One scrollable page per step, and Back / Next under it."""
        side = QWidget()
        self.sidebar = side
        side.setMinimumWidth(300)
        side.setMaximumWidth(560)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(8, 8, 4, 8)

        self._step_title = QLabel()
        self._step_title.setWordWrap(True)
        layout.addWidget(self._step_title)

        mode_box = QWidget()
        mode_box.setMaximumHeight(48)
        mode_row = QHBoxLayout(mode_box)
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.addWidget(QLabel("Mode:"))
        mode_row.addWidget(with_help(self.mode, self._mode_topic), 1)

        self.run_history = QListWidget()
        self.run_history.setMaximumHeight(220)
        self.run_history.setToolTip("Saved runs for this project; select one to review its output.")
        self.run_history.itemClicked.connect(self._open_history_result)
        from .panels.common import CollapsibleSection
        history_section = CollapsibleSection("Saved runs", expanded=False)
        history_section.body_layout.addWidget(self.run_history)
        self._pages = QStackedWidget()
        self.method_inspector = QWidget()
        QVBoxLayout(self.method_inspector).setContentsMargins(0, 0, 0, 0)
        self.method_inspector.hide()
        self.parameter_dialog = QDialog(self)
        self.parameter_dialog.setWindowTitle("Function settings")
        self.parameter_dialog.resize(460, 560)
        parameter_layout = QVBoxLayout(self.parameter_dialog)
        parameter_scroll = QScrollArea()
        parameter_scroll.setWidgetResizable(True)
        parameter_scroll.setFrameShape(QFrame.NoFrame)
        parameter_scroll.setWidget(self.method_inspector)
        parameter_layout.addWidget(parameter_scroll, 1)
        from .help import HelpButton
        self._parameter_topic = text_topic("Function settings", "Select a function in the local network to view its parameters and sourced explanation.")
        parameter_layout.addWidget(HelpButton(lambda: self._parameter_topic))
        done = QDialogButtonBox(QDialogButtonBox.Close)
        done.rejected.connect(self.parameter_dialog.close)
        parameter_layout.addWidget(done)
        self.parameter_dialog.finished.connect(lambda *_: self._restore_inspector())
        self.method_settings = QWidget(self)
        settings_layout = QVBoxLayout(self.method_settings)
        for widget in (self.core, self.material, self.filters, self.schedules, self.variants):
            settings_layout.addWidget(widget)
        self.method_settings.hide()
        self._inspected_widget = None
        pages = (
            (self.design, self.core.volume_box, self.lc, self.objective, self.constraints),
            (QLabel("Select a function to open its settings.\nEnter a block to work in its local network.\nUse the library to add compatible functions."),),
            (mode_box, history_section, self.sg, self.sg2, self.cg, self.clcg, self.cmg, self.msg, self.sens, self.ssg, self.ssg2),
            (self._build_post_box(),),
            (self._build_file_export_box(), self.core.output_section),
        )
        for widgets in pages:
            self._pages.addWidget(self._scroll_page(widgets))
        # Serialized legacy postprocessor lists remain readable without cluttering
        # the initial fixed-threshold UI with future methods.
        self.post.setParent(self)
        self.post.hide()
        layout.addWidget(self._pages, 1)

        nav = QHBoxLayout()
        self._back_btn = QPushButton("‹  Back")
        self._next_btn = QPushButton("Next  ›")
        self._back_btn.clicked.connect(lambda: self.go_to_step(self.current_step() - 1))
        self._next_btn.clicked.connect(lambda: self.go_to_step(self.current_step() + 1))
        nav.addWidget(self._back_btn)
        nav.addStretch(1)
        nav.addWidget(self._next_btn)
        layout.addLayout(nav)
        return side

    def _build_post_box(self):
        """The deliberately minimal v0.2.1 result operation."""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Binary threshold · 0.5\nBelow 0.5 → void; at or above 0.5 → solid."))
        self.export_btn = QPushButton("Execute post-process step")
        self.export_btn.setMinimumHeight(40)
        self.export_btn.clicked.connect(self._apply_binary)
        layout.addWidget(with_help(self.export_btn, lambda: text_topic(
            "Binary threshold", "Convert the current result to 0 or 1 at density 0.5 and immediately update the figure. This changes the result used by export; it does not rerun optimization or re-evaluate the objective.")))
        return box

    def _build_file_export_box(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        self.export_format = QComboBox()
        for label, name in (("STL solid", "export_stl"), ("SVG outline (2D)", "export_svg"),
                            ("DXF outline (2D)", "export_dxf"), ("NumPy density", "npy")):
            self.export_format.addItem(label, name)
        layout.addWidget(self.export_format)
        self.write_export_btn = QPushButton("Export current result…")
        self.write_export_btn.setMinimumHeight(40)
        self.write_export_btn.clicked.connect(self._write_export)
        layout.addWidget(with_help(self.write_export_btn, lambda: text_topic(
            "Export", "Write the current processed result, or the original result if no post-processing was performed, to a chosen folder. File export does not modify the design. Export version control is future work.")))
        self.open_folder_btn = QPushButton("Open the last run's folder")
        self.open_folder_btn.clicked.connect(self._open_last_folder)
        layout.addWidget(self.open_folder_btn)
        self._refresh_export_buttons()
        return box

    def _refresh_export_buttons(self):
        from . import runner
        done = runner.last_run_folder is not None
        self.export_btn.setEnabled(done)
        self.open_folder_btn.setEnabled(done)
        self.write_export_btn.setEnabled(done)
        tip = "" if done else "Available after a Run One has finished."
        self.export_btn.setToolTip(tip)
        self.open_folder_btn.setToolTip(tip)

    def _apply_binary(self):
        import numpy as np

        from . import runner
        if runner.last_run_folder is None or self._result_density is None:
            return
        self._result_density = (self._result_density >= .5).astype(float)
        folder = runner.last_run_folder / "post"
        folder.mkdir(exist_ok=True)
        np.save(folder / "current_design.npy", self._result_density)
        self._draw_current_result(processed=True)
        self._log("[Post] Applied fixed 0.5 threshold; figure and export source updated. Objective has not been re-evaluated.")

    def _draw_current_result(self, processed=False):
        if self._result_density is None:
            return
        label = self._result_objective_label
        if processed:
            label += " (source run; not re-evaluated)"
        self.post_canvas.reset()
        self.post_canvas.set_display(self.display_options.values(), label)
        self.post_canvas.refresh(self._result_density, self._result_objectives, self._result_iteration)
        if self._result_density.ndim == 3:
            self.post_canvas.show_3d(self._result_density, 1 / self._result_config.solver.m, self._log)

    def _write_export(self):
        from dataclasses import replace
        from pathlib import Path

        import numpy as np

        from toporia.engine.postprocess import run_postprocessors
        if self._result_density is None:
            return
        destination = QFileDialog.getExistingDirectory(self, "Export current result to folder")
        if not destination:
            return
        kind = self.export_format.currentData()
        try:
            if kind == "npy":
                np.save(Path(destination) / "design.npy", self._result_density)
            else:
                cfg = replace(self._result_config, output=replace(self._result_config.output, postprocess=[{"type": kind}]))
                from toporia.framework.problem.mesh import make_problem
                problem = make_problem(cfg.scenario, cfg.solver.m)
                # Export the exact selected result. A Boolean difference may
                # intentionally remove regions that were fixed in its inputs.
                problem.passive_elements = np.zeros_like(problem.passive_elements)
                problem.void_elements = np.zeros_like(problem.void_elements)
                done = run_postprocessors(cfg, self._result_density, destination, problem=problem)
                failures = [entry["error"] for entry in done.values() if "error" in entry]
                if failures:
                    raise ValueError("; ".join(failures))
            self.statusBar().showMessage(f"Exported current result to {destination}", 10000)
            self._log(f"[Export] {kind} → {destination}")
        except (OSError, ValueError, ImportError) as error:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export failed", str(error))

    def _on_export(self):
        """Post-process the last design with the current list, and log what was made."""
        from . import runner
        specs = self.post.get_specs()
        if not specs:
            self._log("[Post] Add a post-processor above first.")
            return
        self._log(f"=== Post-processing {runner.last_run_folder} ===")
        try:
            done = runner.postprocess_last(specs, self._log)
        except Exception:
            self._log("\n[ERROR]\n" + traceback.format_exc())
            return
        failed = [key for key, entry in done.items() if "error" in entry]
        self._log(f"— Done: {len(done) - len(failed)} of {len(done)} post-processors —")

    def _open_last_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from . import runner
        if runner.last_run_folder is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(runner.last_run_folder)))

    @staticmethod
    def _scroll_page(widgets):
        """A page that stacks `widgets` from the top and scrolls when the window is short."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(8)
        for widget in widgets:
            layout.addWidget(widget)
        # Long entries (parameter paths, method names) may not widen the sidebar: dropdowns
        # shrink to the space there is and show the whole entry when opened.
        for combo in page.findChildren(QComboBox):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(8)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    def _build_view(self):
        """The live canvas, with the console under it."""
        self.workspace_views = QStackedWidget()
        from .display_options import DisplayOptions
        self.display_options = DisplayOptions(self)
        self.display_options.changed.connect(self._set_display_options)
        self.problem_preview = LiveCanvas()
        self.problem_editor = ProblemEditor()
        self.problem_editor.changed.connect(self._on_scene_changed)
        self.problem_editor.copy_requested.connect(self.copy_to_custom)
        self.problem_editor.view_changed.connect(lambda values: self.project.view.update(values) if hasattr(self, "project") else None)
        self.workspace_views.addWidget(self.problem_editor)
        self.method_view = MethodWorkspace()
        self.method_view.selected.connect(self._inspect_method_node)
        self.method_view.arranged.connect(self._remember_diagram)
        self.method_view.stage_requested.connect(self._select_stage)
        self.method_view.add_requested.connect(self._add_function)
        self.method_view.context_changed.connect(lambda *_: self._restore_inspector())
        self.workspace_views.addWidget(self.method_view)
        runner_page = QWidget()
        runner_layout = QVBoxLayout(runner_page)
        # The action belongs to Runner rather than the persistent navigation bar.
        runner_layout.addWidget(self.run_btn, alignment=Qt.AlignLeft)
        self.run_status = QLabel("Ready to run")
        self.run_status.setWordWrap(True)
        self.run_progress = QProgressBar()
        self.run_progress.setFormat("%v / %m iterations")
        self.run_progress.hide()
        display_button = QPushButton("Display options…")
        display_button.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        display_button.clicked.connect(self.display_options.show)
        runner_layout.addWidget(display_button, alignment=Qt.AlignRight)
        runner_layout.addWidget(self.run_status)
        runner_layout.addWidget(self.run_progress)
        view = QSplitter(Qt.Vertical)
        runner_layout.addWidget(view, 1)
        self.canvas = LiveCanvas()
        view.addWidget(self.canvas)
        log_box = QWidget()
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(4, 0, 4, 4)
        log_layout.addWidget(QLabel("Console output"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Courier New", 9))
        log_layout.addWidget(self.log)
        view.addWidget(log_box)
        view.setStretchFactor(0, 1)
        view.setSizes([620, 180])
        self.workspace_views.addWidget(runner_page)
        post_page = QWidget()
        post_layout = QVBoxLayout(post_page)
        post_display = QPushButton("Display options…")
        post_display.clicked.connect(self.display_options.show)
        post_layout.addWidget(post_display, alignment=Qt.AlignRight)
        self.post_progress = QProgressBar()
        self.post_progress.setFormat("%v / %m iterations")
        self.post_progress.hide()
        post_layout.addWidget(self.post_progress)
        self.post_canvas = LiveCanvas()
        post_layout.addWidget(self.post_canvas, 1)
        self.workspace_views.addWidget(post_page)
        export_page = QWidget()
        export_layout = QVBoxLayout(export_page)
        export_label = QLabel("Export the current result\nChoose a format and destination on the left.")
        export_label.setAlignment(Qt.AlignCenter)
        export_layout.addWidget(export_label)
        self.workspace_views.addWidget(export_page)
        self.blank_setup = BlankSetup()
        self.blank_setup.changed.connect(self._remember_blank_setup)
        self.blank_setup.completed.connect(self._complete_blank_setup)
        self.workspace_views.addWidget(self.blank_setup)
        self.pipeline.setParent(self)
        self.pipeline.hide()
        return self.workspace_views

    def _set_display_options(self, options):
        if hasattr(self, "project"):
            self.project.view["display"] = options
        self.run_progress.setVisible(options["iteration_graph"])
        self.post_progress.setVisible(options["iteration_graph"])
        for canvas in (self.canvas, self.post_canvas):
            canvas.set_display(options)
        if not options["live"]:
            self._pending_iteration = None

    def set_appearance(self, mode, *, persist=True):
        from PySide6.QtWidgets import QApplication, QMessageBox

        from .appearance import apply_appearance
        try:
            apply_appearance(QApplication.instance(), mode, persist=persist)
        except OSError as error:
            QMessageBox.warning(self, "Appearance preference", str(error))

    def refresh_appearance(self):
        from PySide6.QtWidgets import QApplication

        from .appearance import refresh_icons
        mode = QApplication.instance().property("appearance") or "basic"
        for key, action in getattr(self, "appearance_actions", {}).items():
            action.setChecked(key == mode)
        if hasattr(self, "method_view"):
            self.method_view.refresh_appearance()
        if hasattr(self, "problem_editor"):
            self.problem_editor.refresh_appearance()
            self.problem_editor.spatial.refresh_appearance()
        for name in ("canvas", "post_canvas", "problem_preview"):
            if hasattr(self, name):
                getattr(self, name).refresh_appearance()
        if hasattr(self, "home"):
            self.home.refresh_appearance()
        if hasattr(self, "pipeline"):
            self.pipeline.update()
        refresh_icons(self)

    @staticmethod
    def _objective_label(cfg):
        if cfg is None:
            return "Objective"
        from toporia.plugins.responses import RESPONSES
        return RESPONSES.get(cfg.scenario.objective.get("type", "compliance")).label

    def _on_scene_changed(self, scenario, objects):
        """Preserve explicit geometry while updating generated domain/mesh controls."""
        from dataclasses import replace
        self.project.objects = objects
        self._base_cfg = replace(self._base_cfg, scenario=replace(scenario, regions=objects))
        self.design._Lx, self.design._Ly = scenario.Lx, scenario.Ly
        self.design._show_counts()
        self._refresh_pipeline()
        self._preview_timer.start()

    def _remember_diagram(self, positions):
        """Persist presentation coordinates independently of the computation graph."""
        if hasattr(self, "project"):
            self.project.view["method_positions"] = positions

    def _inspect_method_node(self, node):
        """Reveal the existing generated controls for a selected diagram block."""
        if node.kind == "domain":
            self.go_to_step(0)
            return
        if node.kind == "export":
            self.go_to_step(4)
            return
        widgets = {"design": self.design.representation, "filter": self.filters,
                   "material": self.material, "physics": self.core._model_row, "updater": self.core._updater_row,
                   "method": self.core, "objective": self.objective,
                   "constraint": self.constraints, "budget": self.core.volume_box,
                   "convergence": self.core._convergence, "schedule": self.schedules,
                   "variants": self.variants, "postprocessor": self.post}
        widget = widgets.get(node.kind)
        if self._inspected_widget and self._inspected_widget[0] is widget:
            self._restore_inspector()
            return
        self._restore_inspector()
        if widget is not None:
            if widget in (self.core._model_row, self.core._updater_row, self.material, self.core):
                # Keep saved-project adapters while offering one representative
                # method per stage in this deliberately minimal GUI release.
                for combo in widget.findChildren(QComboBox):
                    if hasattr(combo.view(), "setRowHidden"):
                        for i in range(combo.count()):
                            combo.view().setRowHidden(i, i != combo.currentIndex())
            from .panels.common import CollapsibleSection
            if not self._pages.widget(1).isAncestorOf(widget):
                parent = widget.parentWidget()
                original = parent.layout()
                self._inspected_widget = (widget, original, original.indexOf(widget))
                original.removeWidget(widget)
                self.method_inspector.layout().addWidget(widget)
                self.method_inspector.show()
                widget.show()
            for section in widget.findChildren(CollapsibleSection):
                section.set_expanded(True)
            from .help import plugin_topic
            self._parameter_topic = plugin_topic(node.cls) if node.cls else text_topic(node.title, node.label)
            self.parameter_dialog.setWindowTitle(node.title + " · " + node.label)
            self.parameter_dialog.show()
            self.parameter_dialog.raise_()
            widget.setFocus()
        else:
            from .help import HelpWindow, plugin_topic
            topic = plugin_topic(node.cls) if node.cls else text_topic(node.title, node.label)
            HelpWindow.instance(self).show_topic(topic)

    def _restore_inspector(self):
        """Return borrowed settings to their workspace when leaving the Method step."""
        if self._inspected_widget is not None:
            widget, layout, index = self._inspected_widget
            self.method_inspector.layout().removeWidget(widget)
            layout.insertWidget(index, widget)
            widget.show()
            self._inspected_widget = None
        self.method_inspector.hide()
        self.parameter_dialog.hide()

    def _on_filter_reordered(self, mapping):
        """Schedules, variants and study paths continue to follow the same filter."""
        import re

        def remap(value):
            if isinstance(value, str):
                return re.sub(r"filters\[(\d+)\]", lambda m: f"filters[{mapping.get(int(m[1]), int(m[1]))}]", value)
            if isinstance(value, dict):
                return {key: remap(item) for key, item in value.items()}
            if isinstance(value, list):
                return [remap(item) for item in value]
            return value

        study = remap(self._capture_study())
        schedules = remap(self.schedules.get_specs())
        variants = remap(self.variants.get_spec())
        self._refresh_parameter_paths()
        self.schedules.load_specs(schedules)
        self.variants.load_spec(variants)
        self._restore_study(study)

    def _build_overview(self):
        """The pipeline, always in view, so every step's choices are visible together."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setMinimumWidth(20)
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 8, 8, 8)
        layout.addWidget(self.pipeline)
        layout.addStretch(1)
        scroll.setWidget(holder)
        return scroll

    def _wire_panels(self):
        """Keep the parameter dropdowns and the pipeline in step with every panel."""
        # The sweep / compare / sensitivity dropdowns list every parameter path of
        # the current setup, so they are rebuilt whenever the method, the filter
        # pipeline or the number of load cases changes.
        self._sweep_groups = (self.sg, self.sg2, self.cg, self.sens, self.ssg, self.ssg2, self.msg)
        self.lc.cases_changed.connect(self._refresh_parameter_paths)
        for group in (self.design, self.material, self.objective, self.constraints, self.filters, self.schedules):
            group.changed.connect(self._refresh_parameter_paths)
        self.core.method_changed.connect(self._on_method_changed)
        self.design.dims_changed.connect(self._on_dims_changed)
        self.filters.reordered.connect(self._on_filter_reordered)
        self.variants.changed.connect(self._refresh_pipeline)
        self.post.changed.connect(self._refresh_pipeline)
        self.variants.robust_requested.connect(self._use_robust_projection)
        # Any edit of the problem redraws its preview; rows added later are wired as they come.
        self.lc.cases_changed.connect(self._watch_problem_inputs)
        self.lc.cases_changed.connect(lambda *_: self.lc.set_regional(self.project.objects is not None) if hasattr(self, "project") else None)
        self._watch_problem_inputs()

    def _watch_problem_inputs(self, *_):
        """Redraw the problem preview after any edit on the Problem step."""
        page = self._pages.widget(0) if hasattr(self, "_pages") else None
        widgets = page.findChildren(QAbstractSpinBox) + page.findChildren(QComboBox) if page else []
        for widget in widgets:
            if widget.property("previewWired"):
                continue
            signal = widget.currentIndexChanged if isinstance(widget, QComboBox) else widget.valueChanged
            signal.connect(lambda *_: self._preview_timer.start())   # the value is not a delay
            widget.setProperty("previewWired", True)
        self._preview_timer.start()

    def show_problem(self):
        """Draw the problem as currently set up, unless a run is drawing (slicer-style preview)."""
        if self._running:
            return
        if self._blank_pending():
            return
        from .config import build_config

        try:
            cfg = build_config(self.core, self.lc, self.filters, base_cfg=self._base_cfg, design=self.design)
        except (ValueError, KeyError) as error:
            self._log(f"[Preview] {error}")
            return
        title = self.project.name if hasattr(self, "project") else self.config_combo.currentText()
        self.problem_editor.load(cfg.scenario, self.project.objects, self.project.benchmark is not None)
        self._update_preflight()
        if self.project.objects is None:
            self.problem_preview.show_problem(cfg.scenario, cfg.solver.m, title)
            self.canvas.show_problem(cfg.scenario, cfg.solver.m, title)

    def _update_preflight(self):
        """Explain definition/compatibility problems before starting an optimisation."""
        from .preflight import problems
        issues = problems(self.current_config(), check_mesh=True)
        self.problem_editor.validation.setText("\n".join(issues) if issues else "Ready · physical definition and selected method are compatible.")

    # ── Steps ─────────────────────────────────────────────────────────────────

    def current_step(self):
        """Index of the step whose settings are shown (0 = Problem)."""
        return self._pages.currentIndex()

    def go_to_step(self, index):
        """Show step `index`'s settings; out-of-range indices are ignored."""
        if self._running and index != 2:
            return
        if not 0 <= index < len(STEPS):
            return
        if self._blank_pending() and index != 0:
            return
        if hasattr(self, "root_pages"):
            self.root_pages.setCurrentIndex(1)
            self.navigation_bar.show()
        if index != 1:
            self._restore_inspector()
        self._pages.setCurrentIndex(index)
        self.sidebar.setVisible(index != 1 and not self._blank_pending())
        self.workspace_views.setCurrentIndex(index)
        if self._blank_pending():
            self.workspace_views.setCurrentWidget(self.blank_setup)
        if index == 1:
            QTimer.singleShot(0, self.method_view.fit)
        self._step_buttons.button(index).setChecked(True)
        name, about = STEPS[index]
        self._step_title.setText(f"<b>{index + 1}. {name}</b><br><span style='color:gray'>{about}</span>")
        self._back_btn.setEnabled(index > 0)
        self._next_btn.setEnabled(index < len(STEPS) - 1)
        if index == 0:
            self._preview_timer.start()   # back on the problem: show it as it is set up
        following = STEPS[index + 1][0] if index < len(STEPS) - 1 else "Next"
        self._next_btn.setText(f"{following}  ›".replace("&", "&&"))

    def _mode_topic(self):
        """Help on the selected kind of run."""
        mode = self.mode.currentText()
        what, source = MODES[mode]
        return text_topic(f"Mode: {mode}", what, source)

    def _show_run_label(self):
        """'▶  Run', naming the mode when it is not a single run."""
        mode = self.mode.currentText()
        if hasattr(self.mode.view(), "setRowHidden"):
            for i in range(self.mode.count()):
                self.mode.view().setRowHidden(i, i != self.mode.currentIndex())
        self.run_btn.setText("▶  Run" if mode == "Run One" else f"▶  Run: {mode}")
        self.run_btn.setEnabled(not self._blank_pending())

    def _report_plugin_errors(self):
        """Log every plugin that failed to load; the others are all usable."""
        from toporia.api import plugin_errors

        for kind, where, message in plugin_errors():
            self._log(f"[Plugin not loaded] {kind} {where}: {message}")

    # ── Slots — methods connected to UI signals ───────────────────────────────

    def _on_config_changed(self, name):
        """Load a configuration preset: update self._base_cfg and populate the widgets."""
        from toporia.plugins.problems import get_run

        try:
            cfg = get_run(name)
        except Exception as e:
            self._log(f"[Config error] {e}")
            return
        self.project = Project(name, cfg, benchmark=name)
        self._loading_stage = True
        try:
            self._populate_run(cfg)
        finally:
            self._loading_stage = False
        self._refresh_pipeline()
        self._apply_problem_lock()
        if hasattr(self, "notes"):
            self.notes.clear()
            self._saved_state = self._capture_project().payload()
            self._clean_geometry = self.project.objects
            self._show_blank_setup()

    def _on_method_changed(self, name):
        """Adapt the panels to what the selected method can do."""
        from toporia.plugins.filters import FILTERS
        from toporia.plugins.methods import method_class

        capabilities = method_class(name).capabilities
        self.filters.set_allowed(FILTERS.names() if capabilities.accepts_filters else [])
        self.design.set_representation_available(capabilities.accepts_representation)
        from toporia.framework.parts.composition import ComposedMethod

        self.variants.setVisible(
            issubclass(method_class(name), ComposedMethod)
        )  # a whole method evaluates itself
        self.material.setVisible(capabilities.accepts_interpolation)
        self.objective.set_allowed(capabilities.objectives)
        enforceable = capabilities.constraints if capabilities.max_constraints != 0 else []
        self.constraints.set_allowed(enforceable, self._why_no_constraints(name))
        self._refresh_parameter_paths()

    def _why_no_constraints(self, name):
        """In words: why the method enforces nothing besides the volume budget, and what would."""
        from toporia.framework.parts.composition import ComposedMethod
        from toporia.plugins.methods import method_class
        from toporia.plugins.updaters import UPDATERS

        cls = method_class(name)
        if not issubclass(cls, ComposedMethod):
            return f"{cls.label} enforces only the volume budget."
        if not cls.model.capabilities.constraints:
            return f"{cls.model.label} computes no constraint besides the volume budget."
        able = [u.label for u in UPDATERS.classes() if u.max_constraints != 0]
        return (
            f"{cls.updater.label} enforces only the volume budget. "
            f"Updaters that enforce constraints: {', '.join(able)}."
        )

    def _on_dims_changed(self, dims):
        """2-D <-> 3-D: keep the updater, pick a physics model that works in that dimension, show load elevations."""
        self.lc.set_3d(dims == 3)
        from toporia.framework.parts.composition import ComposedMethod
        from toporia.plugins.methods import method_class
        from toporia.plugins.models import MODELS

        cls = method_class(self.core.method_name())
        if issubclass(cls, ComposedMethod) and dims not in cls.model.capabilities.dims:
            model = next((m for m in MODELS.classes() if dims in m.capabilities.dims), None)
            if model is not None:
                self.core.select_method(f"{model.name}+{cls.updater.name}")
                self._log(f"[{dims}-D] physics model switched to {model.label}")
        self._refresh_pipeline()

    def _refresh_parameter_paths(self, *_):
        """Rebuild every parameter dropdown from the current method, filters and load cases."""
        from toporia.plugins.catalog import parameter_paths, schedulable_paths

        setup = dict(
            objective=self.objective.get_spec(),
            constraints=self.constraints.get_specs(),
            interpolation=self.material.get_spec(),
            representation=self.design.get_spec(),
        )
        self.schedules.set_paths(
            schedulable_paths(self.core.method_name(), self.filters.get_specs(), **setup)
        )
        items = parameter_paths(
            self.core.method_name(),
            self.filters.get_specs(),
            len(self.lc.get_load_cases()),
            schedules=self.schedules.get_specs(),
            **setup,
        )
        if hasattr(self, "project") and self.project.objects is not None:
            items = [(label, path) for label, path in items if not path.startswith("load_cases[") or path.endswith(".weight")]
        for group in self._sweep_groups:
            group.refresh(items)
        self.variants.set_paths(items)
        self._refresh_pipeline()

    def _use_robust_projection(self):
        """Eroded / intermediate / dilated on the first Heaviside filter, adding one when there is none."""
        types = [spec.get("type") for spec in self.filters.get_specs()]
        if "heaviside" not in types:
            self.filters.load_specs([*self.filters.get_specs(), {"type": "heaviside"}])
            types.append("heaviside")
        self._refresh_parameter_paths()
        self.variants.use_robust_projection(types.index("heaviside"))

    def _refresh_pipeline(self):
        """Show the chain the current selections describe, and why any part is unavailable."""
        from toporia.engine.pipeline import pipeline_graph, pipeline_notes, pipeline_stages

        try:
            cfg = self.current_config()
            tree = self._ensure_workflow()
            self._store_active_stage(cfg)
            self.method_view.set_workflow(tree, getattr(self, "_active_stage", None))
            self.method_view.dimensions = 3 if cfg.scenario.Lz else 2
            self.pipeline.show_pipeline(pipeline_stages(cfg), pipeline_notes(cfg.solver.method, cfg),
                                        graph=pipeline_graph(cfg))
            self.method_view.show_pipeline(pipeline_graph(cfg), pipeline_notes(cfg.solver.method, cfg))
            self.msg.set_context(cfg, problems=self.cmg.set_context(cfg))
            self._preview_timer.start()
        except (ValueError, KeyError) as error:
            self.pipeline.show_pipeline([], [f"Cannot describe this selection: {error}"])

    def _on_mode(self, m):
        """Show only the parameter groups relevant to the selected mode."""
        self.sg.setVisible(m == "Sweep")
        self.sg2.setVisible(m == "Sweep 2D")
        self.cg.setVisible(m == "Compare Two")
        self.clcg.setVisible(m == "Compare Load Cases")
        self.cmg.setVisible(m == "Compare Methods")
        self.msg.setVisible(m == "Sweep Methods")
        self.sens.setVisible(m == "Sensitivity")
        self.ssg.setVisible(m == "Sensitivity Sweep")
        self.ssg2.setVisible(m == "Sensitivity Sweep 2D")
        # Hide the shared Load Cases panel in Compare Load Cases mode — the two
        # per-design panels inside clcg replace it completely.
        self.lc.setVisible(m != "Compare Load Cases")
        self._show_run_label()

    def _log(self, text):
        """Append one line to the log box and scroll to the bottom."""
        self.log.moveCursor(QTextCursor.End)
        self.log.insertPlainText(text + "\n")
        self.log.moveCursor(QTextCursor.End)

    def _on_stop(self):
        """Request a stop without blocking the Qt event loop."""
        self.stop_execution()

    def _on_run(self):
        """Start an immutable project snapshot, or stop the current worker."""
        if self._running:
            self.stop_execution()
        else:
            self.start_execution()
