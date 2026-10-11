# apps/gui/window.py — the main application window
#
# MainWindow lays the app out like a slicer: you walk through numbered steps
# along the top, the current step's settings sit in the sidebar, and the view
# of the design is always in the middle.
#
#   ┌───────────────────────────────────────────────────────────────────────────┐
#   │ Toporia  Preset [▼]   1 Problem › 2 Solver › 3 Study › 4 Post & Export [▶ Run] │
#   ├──────────────────┬───────────────────────────────────────┬────────────────┤
#   │ settings of the  │                                       │                │
#   │ current step     │   LiveCanvas (density + convergence)  │  PipelineView  │
#   │                  │                                       │  (what the run │
#   │                  ├───────────────────────────────────────┤   is made of)  │
#   │ [‹ Back][Next ›] │   Console log                         │                │
#   └──────────────────┴───────────────────────────────────────┴────────────────┘
#
# This file contains no optimisation logic and no widget definitions.
# It only wires together the pieces from panels/, canvas.py, and runner.py.

import traceback  # for formatting Python exception messages into readable text

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .canvas import LiveCanvas
from .help import problem_topic, text_topic, with_help
from .panels import (
    CompareLoadCasesParamsGroup,
    CompareMethodsParamsGroup,
    CompareTwoParamsGroup,
    ConstraintsGroup,
    CoreParamsGroup,
    DesignSection,
    LoadCasesGroup,
    MaterialGroup,
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

#: The steps along the top, in the order one walks through them before a run.
STEPS = (
    ("Problem", "What is designed: the design space, the material budget, the loads and supports, "
                "what is optimised and what must hold."),
    ("Solver", "How it is optimised: the physics, the updater, the material law, the filters "
               "and anything that changes during the run."),
    ("Study", "What kind of run: one design, a sweep, a comparison, a sensitivity study, "
              "or a check of every part."),
    ("Post & Export", "What happens to the finished design: clean-up, measurements and files."),
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


class _StopRequested(Exception):
    """Custom exception type raised when the user clicks Stop.
    Using a dedicated type lets us catch it separately from real errors."""


class MainWindow(QMainWindow):
    """The application window: steps and Run along the top, the current step's settings
    on the left, the live canvas and the log in the middle, the pipeline on the right."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Toporia — Topology Optimisation")
        self.resize(1440, 860)
        self._base_cfg = None  # set by _on_config_changed; holds geometry from selected config
        self._stop = False     # flag checked inside on_iter to interrupt the loop

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
        body.addWidget(self._build_overview())
        body.setStretchFactor(1, 1)
        body.setSizes([390, 720, 330])
        outer.addWidget(body, 1)

        self._wire_panels()

        # Wire the configuration dropdown now that self.log exists so error messages work.
        self.config_combo.currentTextChanged.connect(self._on_config_changed)
        self._on_config_changed(self.config_combo.currentText())  # populate widgets from first config

        self._on_mode("Run One")  # hide sweep-specific groups on startup
        self.go_to_step(0)
        self._report_plugin_errors()

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

        row.addWidget(QLabel("Preset:"))
        self.config_combo = QComboBox()
        self.config_combo.addItems(problem_names())
        self.config_combo.setCurrentText(DEFAULT_PROBLEM)
        self.config_combo.setToolTip("A ready-made problem: loads every step below with its settings.")
        row.addWidget(with_help(self.config_combo, lambda: problem_topic(self.config_combo.currentText())))
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
        side.setMinimumWidth(20)
        side.setMaximumWidth(560)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(8, 8, 4, 8)

        self._step_title = QLabel()
        self._step_title.setWordWrap(True)
        layout.addWidget(self._step_title)

        mode_box = QWidget()
        mode_row = QHBoxLayout(mode_box)
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.addWidget(QLabel("Mode:"))
        mode_row.addWidget(with_help(self.mode, self._mode_topic), 1)

        self._pages = QStackedWidget()
        pages = (
            (self.design, self.core.volume_box, self.lc, self.objective, self.constraints),
            (self.core, self.material, self.filters, self.schedules, self.variants),
            (mode_box, self.sg, self.sg2, self.cg, self.clcg, self.cmg, self.sens, self.ssg, self.ssg2),
            (self.post, self.core.output_section),
        )
        for widgets in pages:
            self._pages.addWidget(self._scroll_page(widgets))
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
        view = QSplitter(Qt.Vertical)
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
        return view

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
        self._sweep_groups = (self.sg, self.sg2, self.cg, self.sens, self.ssg, self.ssg2)
        self.lc.cases_changed.connect(self._refresh_parameter_paths)
        for group in (self.design, self.material, self.objective, self.constraints, self.filters, self.schedules):
            group.changed.connect(self._refresh_parameter_paths)
        self.core.method_changed.connect(self._on_method_changed)
        self.design.dims_changed.connect(self._on_dims_changed)
        self.variants.changed.connect(self._refresh_pipeline)
        self.post.changed.connect(self._refresh_pipeline)
        self.variants.robust_requested.connect(self._use_robust_projection)

    # ── Steps ─────────────────────────────────────────────────────────────────

    def current_step(self):
        """Index of the step whose settings are shown (0 = Problem)."""
        return self._pages.currentIndex()

    def go_to_step(self, index):
        """Show step `index`'s settings; out-of-range indices are ignored."""
        if not 0 <= index < len(STEPS):
            return
        self._pages.setCurrentIndex(index)
        self._step_buttons.button(index).setChecked(True)
        name, about = STEPS[index]
        self._step_title.setText(f"<b>{index + 1}. {name}</b><br><span style='color:gray'>{about}</span>")
        self._back_btn.setEnabled(index > 0)
        self._next_btn.setEnabled(index < len(STEPS) - 1)
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
        self.run_btn.setText("▶  Run" if mode == "Run One" else f"▶  Run: {mode}")

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

        from .config import build_config

        try:
            cfg = build_config(
                self.core,
                self.lc,
                self.filters,
                base_cfg=self._base_cfg,
                objective=self.objective,
                constraints=self.constraints,
                interpolation=self.material,
                representation=self.design,
                schedules=self.schedules,
                variants=self.variants,
                postprocess=self.post,
                design=self.design,
            )
            self.pipeline.show_pipeline(pipeline_stages(cfg), pipeline_notes(cfg.solver.method, cfg),
                                        graph=pipeline_graph(cfg))
        except (ValueError, KeyError) as error:
            self.pipeline.show_pipeline([], [f"Cannot describe this selection: {error}"])

    def _on_mode(self, m):
        """Show only the parameter groups relevant to the selected mode."""
        self.sg.setVisible(m == "Sweep")
        self.sg2.setVisible(m == "Sweep 2D")
        self.cg.setVisible(m == "Compare Two")
        self.clcg.setVisible(m == "Compare Load Cases")
        self.cmg.setVisible(m == "Compare Methods")
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
        QApplication.processEvents()  # force Qt to repaint the log immediately

    def _on_stop(self):
        """Called when the user clicks Stop — sets the flag that on_iter checks."""
        self._stop = True
        self._log("Stop requested…")

    def _on_run(self):
        """Called when Run is clicked.  Orchestrates the full run sequence."""
        mode = self.mode.currentText()
        self.log.clear()
        self._log(f"=== {mode} ===")
        self._stop = False

        # Re-label the button as Stop and rewire it to _on_stop.
        # The original connection is disconnected first to avoid double-firing.
        self.run_btn.setText("⏹  Stop")
        self.run_btn.clicked.disconnect()
        self.run_btn.clicked.connect(self._on_stop)
        QApplication.processEvents()

        from . import runner  # imports SciPy-backed optimisation code only when needed

        cfg = runner.build_config(
            self.core,
            self.lc,
            self.filters,
            base_cfg=self._base_cfg,
            objective=self.objective,
            constraints=self.constraints,
            interpolation=self.material,
            representation=self.design,
            schedules=self.schedules,
            variants=self.variants,
            postprocess=self.post,
            design=self.design,
        )

        # on_iter is the per-iteration callback passed into the optimisation scripts.
        # It runs inside the optimisation loop after every solver step.
        last_it = [0]  # list instead of plain int so the nested function can modify it

        def on_iter(d, obj, it):
            """Called after every iteration: honour Stop, redraw the canvas, keep the window responsive."""
            if self._stop:
                raise _StopRequested()  # breaks out of the optimisation loop cleanly
            if it <= last_it[0]:
                self.canvas.reset()  # new sweep cell started — clear the canvas
            last_it[0] = it
            self.canvas.refresh(d, obj, it)
            QApplication.processEvents()  # keep the UI responsive between iterations

        try:
            self.canvas.reset()
            if mode == "Run One":
                density = runner.run_one(cfg, on_iter, self._log)
                if density.ndim == 3:
                    self.canvas.show_3d(density, 1.0 / cfg.solver.m, self._log)
            elif mode == "Check Parts":
                # The conformance test (toporia.checks) on every part of the
                # pipeline above: interfaces, gradients, and the benchmark.
                runner.run_check(cfg, self._log)
            elif mode == "Sweep":
                grid = runner.run_sweep(cfg, self.sg, on_iter, self._log)
                self.canvas.show_grid(grid, f"Sweep: {self.sg.key()}")
            elif mode == "Sweep 2D":
                grid = runner.run_sweep_2d(cfg, self.sg2, on_iter, self._log)
                self.canvas.show_grid(grid, f"Sweep 2D: {self.sg2.row_key()} vs {self.sg2.col_key()}")
            elif mode == "Compare Two":
                img = runner.run_compare_two(cfg, self.cg, on_iter, self._log)
                self.canvas.show_grid(
                    img,
                    f"Compare: {self.cg.key()}  A={self.cg.value_a.value():.3g}"
                    f"  vs  B={self.cg.value_b.value():.3g}",
                )
            elif mode == "Compare Methods":
                grid = runner.run_compare_methods(cfg, self.cmg, on_iter, self._log)
                if grid is not None:
                    self.canvas.show_grid(
                        grid,
                        f"Compare Methods: {cfg.scenario.Lx:g} x {cfg.scenario.Ly:g} mm, "
                        f"{len(self.cmg.selected())} methods",
                    )
            elif mode == "Compare Load Cases":
                img = runner.run_compare_load_cases(cfg, self.clcg, on_iter, self._log)
                self.canvas.show_grid(img, "Compare Load Cases  —  A vs B")
            elif mode == "Sensitivity":
                img = runner.run_sensitivity(cfg, self.sens, on_iter, self._log)
                self.canvas.show_grid(
                    img,
                    f"Sensitivity: {self.sens.key()}"
                    f"  base={self.sens.base_value.value():.3g}"
                    f"  Δ={self.sens.gap.value():.3g}",
                )
            elif mode == "Sensitivity Sweep":
                grid = runner.run_sensitivity_sweep(cfg, self.ssg, on_iter, self._log)
                self.canvas.show_grid(
                    grid,
                    f"Sensitivity Sweep: {self.ssg.sweep_key()}  sens={self.ssg.sens_key()}",
                )
            else:
                grid = runner.run_sensitivity_sweep_2d(cfg, self.ssg2, on_iter, self._log)
                self.canvas.show_grid(
                    grid,
                    f"Sensitivity Sweep 2D:"
                    f"  {self.ssg2.row_sweep_key()} vs {self.ssg2.col_sweep_key()}"
                    f"  sens={self.ssg2.sens_key()}",
                )
        except _StopRequested:
            self._log("— Stopped —")  # user-requested stop: no error shown
        except Exception:
            self._log("\n[ERROR]\n" + traceback.format_exc())  # unexpected error: full traceback
        finally:
            # This block ALWAYS runs — even after an exception.
            # Restore the button to its Run state regardless of how the run ended.
            self.run_btn.clicked.disconnect()
            self.run_btn.clicked.connect(self._on_run)
            self._show_run_label()
        self._log("— Done —")
