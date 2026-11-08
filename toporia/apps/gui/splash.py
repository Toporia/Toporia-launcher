# apps/gui/splash.py — the loading screen shown while the desktop app starts.
#
# Importing every plugin and building the window takes a few seconds and blocks Qt's
# event loop, so the bar moves at checkpoints (progress()) rather than on a timer.  It
# counts down the average of the last few start-up times, kept in the preferences.

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QProgressBar, QVBoxLayout

#: Start-up times remembered for the average.
KEEP = 5
#: Assumed start-up time before any has been measured.
FIRST_GUESS = 5.0

_current = None


def _store():
    from .appearance import preference_store
    return preference_store()


def average_startup():
    """Mean of the last few start-up times, in seconds."""
    try:
        values = [float(v) for v in (_store().value("startup_seconds", []) or [])]
    except (TypeError, ValueError):
        values = []
    return sum(values) / len(values) if values else FIRST_GUESS


def remember_startup(seconds):
    try:
        store = _store()
        values = [float(v) for v in (store.value("startup_seconds", []) or [])]
    except (TypeError, ValueError):
        values = []
    store.setValue("startup_seconds", [*values, round(float(seconds), 2)][-KEEP:])
    store.sync()


class StartupSplash(QFrame):
    """A small frameless window: the name, what is happening, and a bar counting down the usual wait."""

    def __init__(self, version):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedSize(420, 150)
        layout = QVBoxLayout(self)
        title = QLabel(f"<b>Toporia</b> · {version}")
        title.setStyleSheet("font-size: 22px;")
        layout.addWidget(title)
        self.message = QLabel("Starting…")
        layout.addWidget(self.message)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)
        self.remaining = QLabel()
        self.remaining.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.remaining)
        self.started = time.perf_counter()
        self.expected = max(average_startup(), 0.5)
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.move(screen.availableGeometry().center() - self.rect().center())

    def progress(self, message):
        elapsed = time.perf_counter() - self.started
        self.message.setText(message)
        self.bar.setValue(int(1000 * min(elapsed / self.expected, 0.97)))
        left = self.expected - elapsed
        self.remaining.setText(f"about {left:.0f} s left" if left >= 1 else "almost there")
        QApplication.processEvents()

    def finish(self):
        remember_startup(time.perf_counter() - self.started)
        self.close()


def show_splash(version):
    """Show the loading screen; progress() then reports to it until finish_splash()."""
    global _current
    _current = StartupSplash(version)
    _current.show()
    _current.progress("Starting…")
    return _current


def progress(message):
    """A start-up checkpoint; does nothing when no loading screen is shown (tests, scripts)."""
    if _current is not None:
        _current.progress(message)


def finish_splash():
    global _current
    if _current is not None:
        _current.finish()
        _current = None
