# apps/gui/window.py — the main application window
#
# MainWindow assembles all components into the final UI:
#
#   ┌─────────────────────┬──────────────────────────────────────────┐
#   │  Mode dropdown      │                                          │
#   │  PipelineView       │   LiveCanvas (density + convergence)     │
#   │  CoreParamsGroup    │                                          │
#   │  LoadCasesGroup     │                                          │
#   │  SweepParamsGroup   ├──────────────────────────────────────────┤
#   │  Sweep2DParamsGroup │   Console log (QTextEdit, read-only)     │
#   │  [▶ Run / ⏹ Stop]  │                                          │
#   └─────────────────────┴──────────────────────────────────────────┘
#
# This file contains no optimisation logic and no widget definitions.
# It only wires together the pieces from panels/, canvas.py, and runner.py.

import traceback  # for formatting Python exception messages into readable text

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .canvas import LiveCanvas
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


class _StopRequested(Exception):
    """Custom exception type raised when the user clicks Stop.
    Using a dedicated type lets us catch it separately from real errors."""


class MainWindow(QMainWindow):
    """The application window: input panels and the Run/Stop button on the left, the live canvas and the log on the right."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Toporia — Topology Optimisation")
        self.resize(1280, 820)

        # QSplitter lets the user drag the divider between left and right panels.
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)  # the central widget fills the whole window

        # ── Left panel: all controls ──────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(20)
        left.setMaximumWidth(500)
        ll = QVBoxLayout(left)
        ll.setSpacing(6)

        # Configuration row: selects the problem geometry and default solver settings.
        from toporia.plugins.problems import DEFAULT_PROBLEM, problem_names

        crow = QHBoxLayout()
        crow.addWidget(QLabel("Configuration:"))
        self.config_combo = QComboBox()
        self.config_combo.addItems(problem_names())
        self.config_combo.setCurrentText(DEFAULT_PROBLEM)
        crow.addWidget(self.config_combo, 1)
        ll.addLayout(crow)

        # Mode row: selects what kind of run to perform.
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("Mode:"))
        self.mode = QComboBox()
        self.mode.addItems(
            [
                "Run One",
                "Sweep",
                "Sweep 2D",
                "Compare Two",
                "Compare Load Cases",
                "Compare Methods",
                "Sensitivity",
                "Sensitivity Sweep",
                "Sensitivity Sweep 2D",
                "Check Parts",
            ]
        )
        self.mode.currentTextChanged.connect(self._on_mode)  # call _on_mode when selection changes
        mrow.addWidget(self.mode, 1)
        ll.addLayout(mrow)

        self._base_cfg = None  # set by _on_config_changed; holds geometry from selected config

        # QScrollArea lets the parameter groups scroll if the window is too short.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)  # no visible border around the scroll area
        pw = QWidget()
        pl = QVBoxLayout(pw)
        pl.setAlignment(Qt.AlignTop)
        pl.setSpacing(8)  # stack groups from the top
        scroll.setWidget(pw)
        ll.addWidget(scroll, 1)  # stretch=1 so it takes available space

        # Instantiate all parameter group widgets and add them to the scroll area.
        self.pipeline = PipelineView()  # what the run is made of, kept in view above the controls
        self.core = CoreParamsGroup()
        from toporia.plugins.filters import FILTERS
        from toporia.plugins.interpolations import INTERPOLATIONS
        from toporia.plugins.representations import REPRESENTATIONS
        from toporia.plugins.responses import CONSTRAINT_ROLE, OBJECTIVE_ROLE, responses_for

        self.design = DesignSection(REPRESENTATIONS.classes())
        self.material = MaterialGroup(INTERPOLATIONS.classes())
        self.objective = ObjectiveGroup(responses_for(OBJECTIVE_ROLE))
        self.constraints = ConstraintsGroup(responses_for(CONSTRAINT_ROLE))
        self.filters = SpecListGroup(
            "Filters", FILTERS.classes(), initial=[{"type": "density"}], noun="filter"
        )
        from toporia.plugins.schedules import SCHEDULES

        self.schedules = ScheduleListGroup(SCHEDULES.classes())
        self.variants = VariantsGroup()
        from toporia.plugins.postprocessors import POSTPROCESSORS

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
        for g in (
            self.pipeline,
            self.core,
            self.design,
            self.material,
            self.objective,
            self.constraints,
            self.filters,
            self.schedules,
            self.variants,
            self.post,
            self.lc,
            self.sg,
            self.sg2,
            self.cg,
            self.clcg,
            self.cmg,
            self.sens,
            self.ssg,
            self.ssg2,
        ):
            pl.addWidget(g)

        # The sweep / compare / sensitivity dropdowns list every parameter path of
        # the current setup, so they are rebuilt whenever the method, the filter
        # pipeline or the number of load cases changes.
        self._sweep_groups = (self.sg, self.sg2, self.cg, self.sens, self.ssg, self.ssg2)
        self.lc.cases_changed.connect(self._refresh_parameter_paths)
        for group in (
            self.design,
            self.material,
            self.objective,
            self.constraints,
            self.filters,
            self.schedules,
        ):
            group.changed.connect(self._refresh_parameter_paths)
        self.core.method_changed.connect(self._on_method_changed)
        self.design.dims_changed.connect(self._on_dims_changed)
        self.variants.changed.connect(self._refresh_pipeline)
        self.post.changed.connect(self._refresh_pipeline)
        self.variants.robust_requested.connect(self._use_robust_projection)

        # Run/Stop button — the same button toggles between two roles.
        self._stop = False  # flag checked inside on_iter to interrupt the loop
        self.run_btn = QPushButton("▶  Run")
        self.run_btn.setFixedHeight(44)
        f = self.run_btn.font()
        f.setPointSize(12)
        f.setBold(True)
        self.run_btn.setFont(f)
        self.run_btn.clicked.connect(self._on_run)
        ll.addWidget(self.run_btn)
        splitter.addWidget(left)

        # ── Right panel: live canvas + log ────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        self.canvas = LiveCanvas()
        rl.addWidget(self.canvas, 3)  # stretch=3: takes most space
        rl.addWidget(QLabel("Console output"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Courier New", 9))
        self.log.setFixedHeight(160)
        rl.addWidget(self.log)
        splitter.addWidget(right)
        splitter.setSizes([400, 880])  # initial split proportions

        # Wire the configuration dropdown now that self.log exists so error messages work.
        self.config_combo.currentTextChanged.connect(self._on_config_changed)
        self._on_config_changed(self.config_combo.currentText())  # populate widgets from first config

        self._on_mode("Run One")  # hide sweep-specific groups on startup
        self._report_plugin_errors()

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
        from toporia.engine.pipeline import pipeline_notes, pipeline_stages

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
            self.pipeline.show_pipeline(pipeline_stages(cfg), pipeline_notes(cfg.solver.method, cfg))
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
            self.run_btn.setText("▶  Run")
        self._log("— Done —")
