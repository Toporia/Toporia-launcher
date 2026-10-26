# apps/gui/home.py — project entry points and an illustrated, sourced benchmark library.

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from toporia.plugins.problems import get_run, problem_info, problem_names

from .preview import draw_problem


class HomePage(QWidget):
    """Open a saved project, start blank, import a problem, or explore a benchmark."""

    open_requested = Signal()
    blank_requested = Signal()
    import_requested = Signal()
    benchmark_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        title = QLabel("Toporia")
        title.setStyleSheet("font-size: 28px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Define a problem. Build a method. Explore the result."))
        actions = QHBoxLayout()
        for text, signal in (("Open project…", self.open_requested),
                             ("New blank problem", self.blank_requested),
                             ("Import problem…", self.import_requested)):
            button = QPushButton(text)
            button.setMinimumHeight(36)
            button.clicked.connect(signal.emit)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addWidget(QLabel("Benchmark library — open a reference, or copy it to create your own problem."))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a benchmark, feature or reference…")
        layout.addWidget(self.search)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setAlignment(Qt.AlignTop)
        self.cards = []
        for i, name in enumerate(problem_names()):
            about, reference = problem_info(name)
            card = QFrame()
            card.setFrameShape(QFrame.StyledPanel)
            box = QVBoxLayout(card)
            preview = QLabel()
            preview.setAlignment(Qt.AlignCenter)
            preview.setPixmap(_thumbnail(name))
            box.addWidget(preview)
            label = QLabel(name)
            label.setStyleSheet("font-size: 15px; font-weight: 600;")
            box.addWidget(label)
            description = QLabel(about)
            description.setWordWrap(True)
            box.addWidget(description)
            source = QLabel(reference)
            source.setWordWrap(True)
            source.setStyleSheet("color: #81909e; font-size: 11px;")
            box.addWidget(source)
            box.addStretch()
            open_button = QPushButton("Explore benchmark")
            open_button.clicked.connect(lambda _=False, n=name: self.benchmark_requested.emit(n))
            box.addWidget(open_button)
            grid.addWidget(card, i // 3, i % 3)
            self.cards.append((card, f"{name} {about} {reference}".casefold()))
        scroll.setWidget(holder)
        layout.addWidget(scroll, 1)
        self.search.textChanged.connect(self._filter)

    def _filter(self, text):
        """Search descriptions and references as well as benchmark titles."""
        for card, words in self.cards:
            card.setVisible(text.casefold() in words)


def _thumbnail(name):
    """Render a preset without starting a solver or creating result files."""
    figure = Figure(figsize=(3.4, 1.5), dpi=80, facecolor="#f5f7fa")
    canvas = FigureCanvasAgg(figure)
    axis = figure.add_subplot(111)
    draw_problem(axis, get_run(name).scenario, "#253341")
    axis.get_legend().remove() if axis.get_legend() else None
    figure.tight_layout(pad=0.4)
    canvas.draw()
    width, height = canvas.get_width_height()
    return QPixmap.fromImage(QImage(canvas.buffer_rgba(), width, height,
                                   QImage.Format_RGBA8888).copy())
