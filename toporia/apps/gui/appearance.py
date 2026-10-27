"""Application-wide Basic and Sleek themes, using inexpensive Qt styling."""

from PySide6.QtCore import QSettings, QSize
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import QAbstractButton, QApplication, QListWidget

MODES = {"basic": "Basic", "sleek": "Sleek monochrome"}

SLEEK_STYLE = """
QWidget { background-color: #000000; color: #ffffff; }
QPushButton, QToolButton, QLineEdit, QComboBox, QAbstractSpinBox,
QTextEdit, QTextBrowser, QListWidget, QTreeWidget, QGroupBox {
    border: 1px solid #555555; border-radius: 0px;
}
QPushButton, QToolButton { padding: 6px 10px; min-height: 22px; }
QPushButton[entryCard=true] { min-width: 220px; min-height: 140px; }
QToolButton[helpButton=true] {
    padding: 0px; min-width: 20px; min-height: 20px;
    max-width: 20px; max-height: 20px;
}
QPushButton:hover, QToolButton:hover { border-color: #ffffff; background: #161616; }
QPushButton:checked, QToolButton:checked { border-color: #ffffff; background: #242424; }
QWidget:disabled { color: #777777; }
QPushButton:disabled, QToolButton:disabled { border-color: #303030; }
QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus,
QTextEdit:focus, QListWidget:focus, QTreeWidget:focus { border-color: #ffffff; }
QMenu::item:selected, QMenuBar::item:selected { background: #242424; }
QAbstractItemView::item:selected { background: #292929; color: #ffffff; }
QAbstractItemView::item:hover { background: #171717; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px; height: 14px; border: 1px solid #bbbbbb; background: #000000;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked { background: #ffffff; }
QRadioButton::indicator { border-radius: 7px; }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { border-color: #555555; }
QProgressBar { border: 1px solid #777777; text-align: center; }
QProgressBar::chunk { background-color: #ffffff; }
QHeaderView::section { background: #000000; color: #ffffff; border: 1px solid #555555; }
QSplitter::handle { background: #292929; }
QToolTip { background: #111111; color: #ffffff; border: 1px solid #aaaaaa; }
"""


def preference_store():
    return QSettings("Toporia", "GUI")


def saved_appearance():
    mode = preference_store().value("appearance", "basic")
    return mode if isinstance(mode, str) and mode in MODES else "basic"


def themed_icon(original):
    if QApplication.instance().property("appearance") != "sleek" or original.isNull():
        return original
    result = QIcon()
    for size in (16, 20, 24, 32):
        for state in (QIcon.Normal, QIcon.Disabled):
            image = original.pixmap(QSize(size, size)).toImage().convertToFormat(QImage.Format_ARGB32)
            for x in range(image.width()):
                for y in range(image.height()):
                    source = image.pixelColor(x, y)
                    luminance = (299 * source.red() + 587 * source.green() + 114 * source.blue()) // 1000
                    shade = int((255 - luminance) * (1 if state == QIcon.Normal else .55))
                    image.setPixelColor(x, y, QColor(shade, shade, shade, source.alpha()))
            result.addPixmap(QPixmap.fromImage(image), state)
    return result


def refresh_icons(window):
    for button in window.findChildren(QAbstractButton):
        if not hasattr(button, "_basic_icon"):
            button._basic_icon = button.icon()
        button.setIcon(themed_icon(button._basic_icon))
    for listing in window.findChildren(QListWidget):
        for index in range(listing.count()):
            item = listing.item(index)
            if not hasattr(item, "_basic_icon"):
                item._basic_icon = item.icon()
            item.setIcon(themed_icon(item._basic_icon))


def colours(widget):
    """Chrome colors only; scientific support/load/result colors stay meaningful."""
    app = QApplication.instance()
    if app is not None and app.property("appearance") == "sleek":
        return {"background": QColor("#000000"), "surface": QColor("#000000"),
                "text": QColor("#ffffff"), "muted": QColor("#b0b0b0"),
                "border": QColor("#777777"), "accent": QColor("#ffffff")}
    palette = app.palette() if app is not None else widget.palette()
    return {"background": palette.color(QPalette.Window), "surface": palette.color(QPalette.Base),
            "text": palette.color(QPalette.Text), "muted": palette.color(QPalette.PlaceholderText),
            "border": palette.color(QPalette.Mid), "accent": palette.color(QPalette.Highlight)}


def apply_appearance(app, mode, *, persist=False):
    if mode not in MODES:
        raise ValueError(f"Unknown appearance mode: {mode}")
    if not hasattr(app, "_toporia_basic_palette"):
        app._toporia_basic_palette = QPalette(app.palette())
    app.setProperty("appearance", mode)
    app.setStyleSheet("")
    palette = QPalette(app._toporia_basic_palette)
    if mode == "sleek":
        for role in (QPalette.Window, QPalette.Base, QPalette.AlternateBase, QPalette.Button,
                     QPalette.ToolTipBase):
            palette.setColor(role, QColor("#000000"))
        for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText, QPalette.ToolTipText,
                     QPalette.BrightText):
            palette.setColor(role, QColor("#ffffff"))
            palette.setColor(QPalette.Disabled, role, QColor("#777777"))
        palette.setColor(QPalette.Highlight, QColor("#ffffff"))
        palette.setColor(QPalette.HighlightedText, QColor("#000000"))
        palette.setColor(QPalette.PlaceholderText, QColor("#999999"))
        palette.setColor(QPalette.Link, QColor("#ffffff"))
        palette.setColor(QPalette.LinkVisited, QColor("#bbbbbb"))
    app.setPalette(palette)
    if mode == "sleek":
        app.setStyleSheet(SLEEK_STYLE)
    # Font-only local style sheets can retain an inherited dark palette after
    # the application sheet is removed. Reset chrome palettes explicitly.
    for widget in app.allWidgets():
        widget.setPalette(palette)
        if widget.styleSheet():
            widget.style().unpolish(widget)
            widget.style().polish(widget)
    for window in app.topLevelWidgets():
        if hasattr(window, "refresh_appearance"):
            window.refresh_appearance()
    if persist:
        settings = preference_store()
        settings.setValue("appearance", mode)
        settings.sync()
        if settings.status() != QSettings.NoError:
            raise OSError("Could not save the appearance preference")


def add_appearance_menu(window, view_menu):
    menu = view_menu.addMenu("Appearance")
    window.appearance_actions = {}
    window.appearance_group = QActionGroup(window)
    for mode, title in MODES.items():
        action = QAction(title, window)
        action.setCheckable(True)
        action.setChecked(mode == (QApplication.instance().property("appearance") or "basic"))
        window.appearance_group.addAction(action)
        action.triggered.connect(lambda _=False, value=mode: window.set_appearance(value))
        menu.addAction(action)
        window.appearance_actions[mode] = action
