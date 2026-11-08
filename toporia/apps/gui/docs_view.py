# apps/gui/docs_view.py — the documentation, readable inside the app (Home > Docs).
#
# The guides are the repository's own Markdown files, rendered as they are, so the app
# and the repository never disagree.  Links between them work; web links open in the
# browser.

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QTextBrowser, QWidget

ROOT = Path(__file__).resolve().parents[3]

#: (title, file, what it is for), in reading order.
GUIDES = (
    ("Start here", "README.md", "What Toporia is, what it does and what it does not do yet."),
    ("Installation", "docs/installation.md", "Step by step, with fixes for common problems."),
    ("Quick start", "docs/quickstart.md", "Change or extend Toporia, starting today."),
    ("Using the desktop app", "docs/gui-workflow.md", "From a problem to an exported design."),
    ("How the code fits together", "toporia/README.md", "The layers and the life of a run."),
    ("Adding a function", "docs/writing-plugins.md", "Every kind of part, with a worked example."),
    ("The library", "toporia/plugins/LIBRARY.md", "Every function, where it comes from, what is still to add."),
    ("Research guide", "docs/research/README.md", "Paper targets, equations and reproduction evidence."),
)


class DocsView(QWidget):
    """A list of guides and a reader for the chosen one."""

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        self.list = QListWidget()
        self.list.setMaximumWidth(280)
        for title, path, about in GUIDES:
            if (ROOT / path).is_file():
                item = QListWidgetItem(title, self.list)
                item.setData(256, str(ROOT / path))        # Qt.UserRole
                item.setToolTip(about)
        row.addWidget(self.list)
        self.reader = QTextBrowser()
        self.reader.setOpenLinks(False)                    # we decide: guides here, the web in the browser
        self.reader.anchorClicked.connect(self._follow)
        row.addWidget(self.reader, 1)
        self.list.currentItemChanged.connect(lambda item, _: item and self.show_file(Path(item.data(256))))
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            row.addWidget(QLabel("The documentation is not part of this installation."))

    def show_file(self, path):
        path = Path(path)
        kind = QTextDocument.MarkdownResource if path.suffix.lower() == ".md" else QTextDocument.HtmlResource
        self.reader.setSource(QUrl.fromLocalFile(str(path)), kind)
        self.current = path

    def _follow(self, url):
        if url.scheme() in ("http", "https", "mailto"):
            QDesktopServices.openUrl(url)
            return
        target = Path(url.toLocalFile()) if url.isLocalFile() else (self.current.parent / url.path()).resolve()
        if target.suffix.lower() in (".md", ".html", ".htm") and target.is_file():
            self.show_file(target)
            if url.fragment():
                self.reader.scrollToAnchor(url.fragment())
        elif target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))      # a figure, a PDF, a folder
