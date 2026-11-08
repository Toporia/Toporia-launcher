"""Presentation settings shared by the runner and post-processor."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QLabel, QSpinBox

DEFAULTS = {"live": True, "interval": 1, "volume": True, "iteration": True,
            "objective": True, "volume_graph": False, "objective_graph": True,
            "iteration_graph": False, "cloud3d": True}


def validate_display(values):
    if not isinstance(values, dict) or set(values) - DEFAULTS.keys():
        raise ValueError("Unknown result-display settings")
    merged = {**DEFAULTS, **values}
    if type(merged["interval"]) is not int or not 1 <= merged["interval"] <= 100000:
        raise ValueError("Display interval must be an integer from 1 to 100000")
    if any(type(v) is not bool for k, v in merged.items() if k != "interval"):
        raise ValueError("Display switches must be booleans")
    return merged


class DisplayOptions(QDialog):
    changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Result display")
        layout = QGridLayout(self)
        self.controls = {}
        live = self.controls["live"] = QCheckBox("Update the design while running")
        layout.addWidget(live, 0, 0, 1, 3)
        self.interval = QSpinBox()
        self.interval.setRange(1, 100000)
        self.interval.setSuffix(" iteration(s)")
        layout.addWidget(QLabel("Update every"), 1, 0)
        layout.addWidget(self.interval, 1, 1, 1, 2)
        layout.addWidget(QLabel("Statistic"), 2, 0)
        layout.addWidget(QLabel("Show value"), 2, 1)
        layout.addWidget(QLabel("Show graph"), 2, 2)
        for row, (key, title) in enumerate((("volume", "Volume fraction"), ("iteration", "Iterations"),
                                           ("objective", "Objective (named in results)")), 3):
            layout.addWidget(QLabel(title), row, 0)
            for col, suffix in ((1, ""), (2, "_graph")):
                checkbox = self.controls[key + suffix] = QCheckBox()
                checkbox.setAccessibleName(title + (" value" if col == 1 else " graph"))
                checkbox.toggled.connect(self._emit)
                layout.addWidget(checkbox, row, col)
        self.controls["iteration_graph"].setToolTip("A progress bar against the maximum iteration count.")
        cloud = self.controls["cloud3d"] = QCheckBox("Show 3-D designs as a density cloud (otherwise the 0.5 surface)")
        cloud.setToolTip("A cloud shows the whole field, more opaque where denser; the surface shows only "
                         "where the density crosses 0.5. Drag either to rotate.")
        cloud.toggled.connect(self._emit)
        layout.addWidget(cloud, 6, 0, 1, 3)
        self.interval.valueChanged.connect(self._emit)
        live.toggled.connect(self._emit)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.hide)
        layout.addWidget(buttons, 7, 0, 1, 3)
        from .help import HelpButton, text_topic
        layout.addWidget(HelpButton(lambda: text_topic("Result display",
            "Volume fraction is the mean physical density over the original rectangular mesh. Solid density is dark in Basic and white in Sleek; void is the opposite. The objective is the selected named response; its values come from optimization evaluations. Iterations count completed optimization steps. The optional iteration graph is a progress bar against the configured maximum, hidden by default. Live display can be disabled or updated every N iterations; the final result is always shown. A finished 3-D design shows as a density cloud (every element with material, more opaque where denser) or as the 0.5 surface. Post-processing updates geometry and volume but does not re-evaluate the objective.")), 8, 2)
        self._loading = False
        self.load({})

    def values(self):
        return {**{key: widget.isChecked() for key, widget in self.controls.items()}, "interval": self.interval.value()}

    def load(self, values):
        values = validate_display(values)
        self._loading = True
        for key, widget in self.controls.items():
            widget.setChecked(values[key])
        self.interval.setValue(values["interval"])
        self._loading = False

    def _emit(self, *_):
        if not self._loading:
            self.changed.emit(self.values())
