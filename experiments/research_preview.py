"""Offscreen visual QA for the actual preset Help window.

python -m experiments.research_preview
Writes screenshots under ignored results/research/preview, opens no desktop UI.
"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont, QFontDatabase, QTextCursor
from PySide6.QtWidgets import QApplication, QTextBrowser

from toporia.apps.gui.help import HelpWindow, problem_topic


def main():
    app = QApplication.instance() or QApplication([])
    # Offscreen Windows Qt may have no system fonts in the sandbox. Use the
    # already bundled Matplotlib font for QA only; do not change application UI.
    from matplotlib import get_data_path
    font_id = QFontDatabase.addApplicationFont(str(Path(get_data_path()) / "fonts/ttf/DejaVuSans.ttf"))
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setFont(QFont(families[0], 10))
    output = Path(__file__).resolve().parents[1] / "results/research/preview"
    output.mkdir(parents=True, exist_ok=True)
    window = HelpWindow()
    for kind in ("Density", "Sensitivity"):
        window.resize(520, 440)
        window.show_topic(problem_topic("Paper: top88 Fig. 3(a) - " + kind))
        app.processEvents()
        window.grab().save(str(output / f"{kind.lower()}-setup.png"))
        window.browser.find("Mathematics")
        cursor = window.browser.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock)
        window.browser.setTextCursor(cursor)
        window.browser.ensureCursorVisible()
        scroll = window.browser.verticalScrollBar()
        # Put the math heading near the top, rather than the last visible line.
        scroll.setValue(min(scroll.maximum(), scroll.value() + window.browser.height() - 55))
        app.processEvents()
        window.grab().save(str(output / f"{kind.lower()}-math.png"))
        scroll.setValue(scroll.maximum())
        app.processEvents()
        window.grab().save(str(output / f"{kind.lower()}-source.png"))
    window.close()
    guide = QTextBrowser()
    guide.resize(1000, 1000)
    guide.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / "docs/research/core.html")))
    guide.show()
    app.processEvents()
    guide.grab().save(str(output / "core-top.png"))
    guide.find("Assign material and solve the state")
    guide.ensureCursorVisible()
    guide.verticalScrollBar().setValue(guide.verticalScrollBar().value() + 500)
    app.processEvents()
    guide.grab().save(str(output / "core-math.png"))
    guide.close()
    print(output)


if __name__ == "__main__":
    main()
