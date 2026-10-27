"""Registry-backed function information shared by Home and nested workspaces."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
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


class FunctionExplorer(QWidget):
    """Browsable encyclopedia populated from installed plugin declarations."""

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
        row.addWidget(self.details, 2)
        layout.addLayout(row, 1)
        for kind, registry in registries().items():
            group = QTreeWidgetItem(self.tree, [kind.capitalize()])
            for cls in registry.classes():
                item = QTreeWidgetItem(group, [cls.label])
                topic = plugin_topic(cls, kind)
                topic.add("Where it belongs", PLACEMENT[kind])
                topic.add("Developer contributions", "Add a registered plugin with its computational contract, parameter declarations, documentation and reference. GUI function authoring is planned for a future release.")
                item.setData(0, Qt.UserRole, topic)
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
        if topic:
            self.details.setHtml(topic.to_html())

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
