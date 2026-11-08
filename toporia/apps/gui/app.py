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


def launch(project_path=None):
    """Start the desktop app and block until its window is closed."""
    app = QApplication(sys.argv)  # one QApplication per process — mandatory
    app.setStyle("Fusion")        # cross-platform look that works on all OS
    from .appearance import apply_appearance, saved_appearance
    apply_appearance(app, saved_appearance())

    # Force the English locale so all spinboxes use "." as the decimal
    # separator regardless of the operating system's regional settings.
    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))

    # The loading screen first: importing the plugins and building the window takes a few seconds.
    from . import GUI_VERSION
    from .splash import finish_splash, progress, show_splash
    show_splash(GUI_VERSION)
    progress("Loading the function library…")
    from .window import MainWindow
    progress("Building the window…")
    win = MainWindow()
    win.show()
    finish_splash()
    if project_path is not None:
        win.open_project(project_path)
    sys.exit(app.exec())


if __name__ == "__main__":
    launch()
