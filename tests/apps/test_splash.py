"""The loading screen counts down the usual start-up time and remembers how long starting took."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from toporia.apps.gui import splash  # noqa: E402


def test_the_bar_counts_down_the_average_of_recent_start_ups():
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    store = splash._store()
    store.setValue("startup_seconds", [4.0, 6.0])
    assert splash.average_startup() == 5.0
    screen = splash.show_splash("test")
    splash.progress("Loading…")
    assert screen.message.text() == "Loading…" and 0 <= screen.bar.value() < 1000
    assert "s left" in screen.remaining.text() or screen.remaining.text() == "almost there"
    splash.finish_splash()
    remembered = [float(v) for v in store.value("startup_seconds")]
    assert len(remembered) == 3 and remembered[:2] == [4.0, 6.0]
    for _ in range(10):
        splash.remember_startup(1.0)
    assert len(store.value("startup_seconds")) == splash.KEEP


def test_checkpoints_do_nothing_without_a_loading_screen():
    splash.progress("no screen")     # tests and scripts build the window without one
