"""Registry-backed function information shared by Home and nested workspaces."""

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from toporia.engine.pipeline import registries

from .help import plugin_topic, text_topic

# Containment describes the computational contract, not Python import ownership.
PLACEMENT = {
    "representation": "Optimization loop / design representation",
    "filter": "Optimization loop / filter chain",
    "interpolation": "Optimization loop / physics / material law",
    "model": "Optimization loop / physics",
    "updater": "Optimization loop / updater",
    "response": "Optimization loop / objective or constraints",
    "schedule": "Optimization loop / parameter continuation",
    "method": "Optimization loop / whole method",
    "postprocessor": "Post-processing or terminal export",
}


#: Where the showcases keep their figures: docs/research/evidence/batch*/<function name>/figure.png.
EVIDENCE = Path(__file__).resolve().parents[3] / "docs" / "research" / "evidence"


def showcase_figure(cls):
    """The figure of the function's own showcase run, or None where there is none (or no docs/)."""
    name = getattr(cls, "name", "")
    if not name or not EVIDENCE.is_dir():
        return None
    return next((path for path in sorted(EVIDENCE.glob(f"batch*/{name}/figure.png"))), None)


def showcase_preset(cls):
    """The research or paper preset made to show this function, or None."""
    from toporia.plugins.compatibility import demo_presets, function_id
    names = demo_presets(function_id(cls))
    # A research showcase is made to show this one function; a paper preset reproduces a figure.
    return next((n for n in names if n.startswith("Research:")), None) or         next((n for n in names if n.startswith("Paper:")), None)


class FunctionExplorer(QWidget):
    """Browsable encyclopedia populated from installed plugin declarations.

    Each function shows what it computes, when to use it, what it works with, its
    parameters and source, the figure of its showcase run, and a button that opens
    that showcase as a project.
    """

    showcase_requested = Signal(str)     # a preset name

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a function, parameter or reference…")
        layout.addWidget(self.search)
        row = QHBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Functions and their location")
        self.tree.setMinimumWidth(270)
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        row.addWidget(self.tree, 1)
        right = QVBoxLayout()
        right.addWidget(self.details, 1)
        self.open_showcase = QPushButton()
        self.open_showcase.hide()
        self.open_showcase.clicked.connect(lambda: self.showcase_requested.emit(self.open_showcase.property("preset")))
        right.addWidget(self.open_showcase)
        row.addLayout(right, 2)
        layout.addLayout(row, 1)
        for kind, registry in registries().items():
            group = QTreeWidgetItem(self.tree, [kind.capitalize()])
            for cls in registry.classes():
                item = QTreeWidgetItem(group, [cls.label])
                topic = plugin_topic(cls, kind)
                topic.add("Where it belongs", PLACEMENT[kind])
                topic.add("Developer contributions", "Add a registered plugin with its computational contract, parameter declarations, documentation and reference. GUI function authoring is planned for a future release.")
                item.setData(0, Qt.UserRole, topic)
                item.setData(0, Qt.UserRole + 1, cls)
                item.setToolTip(0, PLACEMENT[kind])
        independent = QTreeWidgetItem(self.tree, ["Independent infrastructure"])
        for title, description in (
            ("Operating space", "Defines physical domain, supports, loads, material and mesh. Feeds optimization functions."),
            ("Composition", "Sequential functions transform a completed result into the next allowed domain. Parallel functions share an input domain and combine completed results using union, intersection or difference."),
            ("Export", "Terminal file-writing function. Does not change the design. Version control is future work."),
            ("Project and presentation", "Project persistence, geometry import, help, execution logs and display controls support functions without being numerical methods themselves."),
        ):
            item = QTreeWidgetItem(independent, [title])
            item.setData(0, Qt.UserRole, text_topic(title, description))
        self.tree.itemSelectionChanged.connect(self._select)
        self.search.textChanged.connect(self._filter)
        self.details.setHtml(text_topic("Function Explorer", "Choose a function to read what it computes, its parameters and references. The tree is populated from currently installed registries; integration-branch methods appear when integrated.").to_html())

    def _select(self):
        selected = self.tree.selectedItems()
        topic = selected[0].data(0, Qt.UserRole) if selected else None
        cls = selected[0].data(0, Qt.UserRole + 1) if selected else None
        if not topic:
            return
        html = topic.to_html()
        figure = showcase_figure(cls) if cls is not None else None
        if figure is not None:
            url = QUrl.fromLocalFile(str(figure)).toString()
            html += (f"<h3>Its showcase</h3><p><img src='{url}' width='520'></p>"
                     "<p style='font-size:small'>The function's own showcase run, from the research evidence.</p>")
        self.details.setHtml(html)
        preset = showcase_preset(cls) if cls is not None else None
        self.open_showcase.setVisible(preset is not None)
        if preset is not None:
            self.open_showcase.setText(f"Open the showcase: {preset}")
            self.open_showcase.setProperty("preset", preset)

    def _filter(self, value):
        needle = value.casefold()
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            visible = False
            for j in range(group.childCount()):
                item = group.child(j)
                topic = item.data(0, Qt.UserRole)
                match = needle in (item.text(0) + " " + topic.to_html()).casefold()
                item.setHidden(not match)
                visible |= match
            group.setHidden(not visible)
            group.setExpanded(bool(needle))
