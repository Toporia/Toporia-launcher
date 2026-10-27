# apps/gui/home.py — project entry points and an illustrated, sourced benchmark library.

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStyle,
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
        from . import GUI_VERSION
        title = QLabel(f"Toporia · {GUI_VERSION}")
        self.title = title
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
        self.sections = QStackedWidget()
        layout.addWidget(self.sections, 1)
        landing = QWidget()
        landing_layout = QHBoxLayout(landing)
        landing_layout.setAlignment(Qt.AlignCenter)
        self.sections.addWidget(landing)
        self.section_buttons = []
        for text, icon, index in (("Benchmarks", QStyle.SP_DirIcon, 1),
                                  ("Functions", QStyle.SP_FileDialogInfoView, 2)):
            button = QPushButton(text)
            button.setProperty("entryCard", True)
            button.setIcon(self.style().standardIcon(icon))
            button.setMinimumSize(220, 140)
            button.clicked.connect(lambda _=False, i=index: self.open_section(i))
            landing_layout.addWidget(button)
            self.section_buttons.append(button)
        library = QWidget()
        self.sections.addWidget(library)
        library_layout = QVBoxLayout(library)
        back = QPushButton("‹ Home")
        back.clicked.connect(lambda: self.open_section(0))
        library_layout.addWidget(back, alignment=Qt.AlignLeft)
        library_layout.addWidget(QLabel("Benchmark library — open a reference, or copy it to create your own problem."))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a benchmark, feature or reference…")
        library_layout.addWidget(self.search)
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
            # Render previews only when the benchmark section is opened.
            preview.setProperty("benchmark", name)
            box.addWidget(preview)
            label = QLabel(name)
            label.setStyleSheet("font-size: 15px; font-weight: 600;")
            box.addWidget(label)
            description = QLabel(about)
            description.setWordWrap(True)
            box.addWidget(description)
            source = QLabel(reference)
            source.setWordWrap(True)
            source.setStyleSheet("font-size: 11px;")
            box.addWidget(source)
            box.addStretch()
            open_button = QPushButton("Explore benchmark")
            open_button.clicked.connect(lambda _=False, n=name: self.benchmark_requested.emit(n))
            box.addWidget(open_button)
            grid.addWidget(card, i // 3, i % 3)
            self.cards.append((card, f"{name} {about} {reference}".casefold()))
        scroll.setWidget(holder)
        library_layout.addWidget(scroll, 1)
        self.search.textChanged.connect(self._filter)
        from .function_library import FunctionExplorer
        functions = QWidget()
        functions_layout = QVBoxLayout(functions)
        back_functions = QPushButton("‹ Home")
        back_functions.clicked.connect(lambda: self.open_section(0))
        functions_layout.addWidget(back_functions, alignment=Qt.AlignLeft)
        self.explorer = FunctionExplorer()
        functions_layout.addWidget(self.explorer)
        self.sections.addWidget(functions)
        self._thumbnails_loaded = False

    def open_section(self, index):
        self.sections.setCurrentIndex(index)
        if index == 1 and not self._thumbnails_loaded:
            for card, _ in self.cards:
                for label in card.findChildren(QLabel):
                    if label.property("benchmark"):
                        label.setPixmap(_thumbnail(label.property("benchmark")))
            self._thumbnails_loaded = True

    def _filter(self, text):
        """Search descriptions and references as well as benchmark titles."""
        for card, words in self.cards:
            card.setVisible(text.casefold() in words)

    def refresh_appearance(self):
        # Qt style sheets can reset explicit widget minima when unpolished.
        for button in self.section_buttons:
            button.setMinimumSize(220, 140)
        self._thumbnails_loaded = False
        if self.sections.currentIndex() == 1:
            self.open_section(1)


def _thumbnail(name):
    """Render a preset without starting a solver or creating result files."""
    from .appearance import colours
    colors = colours(QApplication.instance())
    figure = Figure(figsize=(3.4, 1.5), dpi=80, facecolor=colors["background"].name())
    canvas = FigureCanvasAgg(figure)
    axis = figure.add_subplot(111)
    axis.set_facecolor(colors["background"].name())
    draw_problem(axis, get_run(name).scenario, colors["text"].name())
    axis.get_legend().remove() if axis.get_legend() else None
    figure.tight_layout(pad=0.4)
    canvas.draw()
    width, height = canvas.get_width_height()
    return QPixmap.fromImage(QImage(canvas.buffer_rgba(), width, height,
                                   QImage.Format_RGBA8888).copy())
