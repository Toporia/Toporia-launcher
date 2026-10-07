# Application bootstrap — the first Qt code that runs.
#
# Responsibilities:
#   1. Tell matplotlib to use the Qt drawing backend (must happen before any
#      matplotlib import elsewhere, so it lives here at the very top)
#   2. Create the QApplication (Qt requires exactly one per process)
#   3. Apply visual style and locale settings
#   4. Create and show the main window, then start the event loop

import sys

# matplotlib must be told which GUI toolkit to draw into BEFORE pyplot is
# imported anywhere.  "QtAgg" means: render into a Qt widget using the Agg
# (anti-grain geometry) rasteriser.
import matplotlib

matplotlib.use("QtAgg")

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from .window import MainWindow


def launch():
    """Start the desktop app and block until its window is closed."""
    app = QApplication(sys.argv)  # one QApplication per process — mandatory
    app.setStyle("Fusion")        # cross-platform look that works on all OS

    # Force the English locale so all spinboxes use "." as the decimal
    # separator regardless of the operating system's regional settings.
    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch()
