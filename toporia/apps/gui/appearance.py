"""Application-wide styles: the system look, four colour schemes and a custom one, via inexpensive Qt styling."""

from PySide6.QtCore import QSettings, QSize
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import QAbstractButton, QApplication, QListWidget

#: Appearance modes, in menu order. "basic" is the system look; "custom" is made with the style maker.
MODES = {"basic": "Basic", "sleek": "Sleek monochrome", "graphite": "Graphite (dark)",
         "paper": "Paper (light)", "blueprint": "Blueprint", "custom": "Custom (style maker)"}

#: Each styled mode as colours; every other chrome colour derives from these.
SCHEMES = {
    "sleek": {"background": "#000000", "surface": "#000000", "text": "#ffffff", "accent": "#ffffff"},
    "graphite": {"background": "#1e2329", "surface": "#262c33", "text": "#e6e9ee", "accent": "#4fa3e0"},
    "paper": {"background": "#f7f5f0", "surface": "#ffffff", "text": "#1f2328", "accent": "#c0572b"},
    "blueprint": {"background": "#0f2a4a", "surface": "#123257", "text": "#e8f1ff", "accent": "#ffd166"},
}
#: The style maker's starting point.
CUSTOM_DEFAULT = SCHEMES["graphite"]


def _mix(a, b, t):
    """Colour a moved a fraction t towards colour b, as #rrggbb."""
    a, b = QColor(a), QColor(b)
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t)).name()


def is_dark(colour):
    colour = QColor(colour)
    return 0.299 * colour.redF() + 0.587 * colour.greenF() + 0.114 * colour.blueF() < 0.5


def full_scheme(base):
    """The four chosen colours plus the ones derived from them: muted, border, hover, checked, …"""
    bg, surface, text, accent = base["background"], base["surface"], base["text"], base["accent"]
    return {**base,
            "muted": _mix(text, bg, 0.35), "border": _mix(text, bg, 0.65), "disabled": _mix(text, bg, 0.55),
            "hover": _mix(surface, text, 0.08), "checked": _mix(surface, text, 0.16),
            "selected": _mix(surface, accent, 0.30), "accent_text": "#000000" if not is_dark(accent) else "#ffffff"}


def custom_scheme():
    """The style maker's colours, from the preferences."""
    import json
    try:
        saved = json.loads(preference_store().value("custom_scheme", "") or "{}")
    except (TypeError, ValueError):
        saved = {}
    return {key: saved.get(key, value) if QColor(str(saved.get(key, value))).isValid() else value
            for key, value in CUSTOM_DEFAULT.items()}


def save_custom_scheme(scheme):
    import json
    store = preference_store()
    store.setValue("custom_scheme", json.dumps({key: QColor(scheme[key]).name() for key in CUSTOM_DEFAULT}))
    store.sync()


def scheme_for(mode):
    """The full colour scheme of a styled mode; None for the system look."""
    if mode == "custom":
        return full_scheme(custom_scheme())
    return full_scheme(SCHEMES[mode]) if mode in SCHEMES else None


def current_scheme():
    app = QApplication.instance()
    return scheme_for(app.property("appearance")) if app is not None else None


STYLE_TEMPLATE = """
QWidget { background-color: $background; color: $text; }
QLineEdit, QComboBox, QAbstractSpinBox, QTextEdit, QTextBrowser, QListWidget, QTreeWidget, QTableWidget {
    background-color: $surface;
}
QPushButton, QToolButton, QLineEdit, QComboBox, QAbstractSpinBox,
QTextEdit, QTextBrowser, QListWidget, QTreeWidget, QGroupBox {
    border: 1px solid $border; border-radius: 0px;
}
QPushButton, QToolButton { padding: 6px 10px; min-height: 22px; }
QGroupBox { margin-top: 10px; padding-top: 8px; }
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left; padding: 0px 4px;
}
QPushButton[entryCard=true] { min-width: 220px; min-height: 140px; }
QToolButton[helpButton=true] {
    padding: 0px; min-width: 20px; min-height: 20px;
    max-width: 20px; max-height: 20px;
}
QPushButton:hover, QToolButton:hover { border-color: $accent; background: $hover; }
QPushButton:checked, QToolButton:checked { border-color: $accent; background: $checked; }
QWidget:disabled { color: $disabled; }
QPushButton:disabled, QToolButton:disabled { border-color: $hover; }
QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus,
QTextEdit:focus, QListWidget:focus, QTreeWidget:focus { border-color: $accent; }
QMenu::item:selected, QMenuBar::item:selected { background: $checked; }
QAbstractItemView::item:selected { background: $selected; color: $text; }
QAbstractItemView::item:hover { background: $hover; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px; height: 14px; border: 1px solid $muted; background: $surface;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked { background: $accent; }
QRadioButton::indicator { border-radius: 7px; }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { border-color: $border; }
QProgressBar { border: 1px solid $border; text-align: center; }
QProgressBar::chunk { background-color: $accent; }
QHeaderView::section { background: $background; color: $text; border: 1px solid $border; }
QSplitter::handle { background: $hover; }
QToolTip { background: $surface; color: $text; border: 1px solid $muted; }
"""


def style_sheet(scheme):
    from string import Template
    return Template(STYLE_TEMPLATE).substitute(scheme)


#: The original monochrome sheet, kept under its old name for anything that imported it.
SLEEK_STYLE = style_sheet(full_scheme(SCHEMES["sleek"]))


def preference_store():
    """The user's GUI preferences; TOPORIA_SETTINGS=<file.ini> keeps them elsewhere (the tests do)."""
    import os
    path = os.environ.get("TOPORIA_SETTINGS")
    return QSettings(path, QSettings.IniFormat) if path else QSettings("Toporia", "GUI")


RECENT_LIMIT = 8


def recent_projects():
    """Recently opened or saved project files, newest first."""
    value = preference_store().value("recent_projects", [])
    paths = [value] if isinstance(value, str) else list(value or [])
    return [p for p in paths if isinstance(p, str)][:RECENT_LIMIT]


def remember_project(path):
    """Put `path` at the top of the recent projects."""
    path = str(path)
    paths = [path, *(p for p in recent_projects() if p != path)][:RECENT_LIMIT]
    settings = preference_store()
    settings.setValue("recent_projects", paths)
    settings.sync()


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
                    shade = int((100 + (255 - luminance) * 155 / 255) * (1 if state == QIcon.Normal else .55))
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
    scheme = current_scheme()
    if scheme is not None:
        return {key: QColor(scheme[key]) for key in ("background", "surface", "text", "muted", "border", "accent")}
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
    scheme = scheme_for(mode)
    if scheme is not None:
        for role in (QPalette.Window, QPalette.Button, QPalette.ToolTipBase):
            palette.setColor(role, QColor(scheme["background"]))
        for role in (QPalette.Base, QPalette.AlternateBase):
            palette.setColor(role, QColor(scheme["surface"]))
        for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText, QPalette.ToolTipText,
                     QPalette.BrightText):
            palette.setColor(role, QColor(scheme["text"]))
            palette.setColor(QPalette.Disabled, role, QColor(scheme["disabled"]))
        palette.setColor(QPalette.Highlight, QColor(scheme["accent"]))
        palette.setColor(QPalette.HighlightedText, QColor(scheme["accent_text"]))
        palette.setColor(QPalette.PlaceholderText, QColor(scheme["muted"]))
        palette.setColor(QPalette.Mid, QColor(scheme["border"]))
        palette.setColor(QPalette.Link, QColor(scheme["accent"]))
        palette.setColor(QPalette.LinkVisited, QColor(scheme["muted"]))
    app.setPalette(palette)
    if scheme is not None:
        app.setStyleSheet(style_sheet(scheme))
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
    menu.addSeparator()
    maker = QAction("Style maker…", window)
    maker.triggered.connect(lambda: open_style_maker(window))
    menu.addAction(maker)
    window.style_maker_action = maker


def open_style_maker(window):
    """Pick four colours, see them at once, and keep them as the Custom style."""
    from .style_maker import StyleMaker
    dialog = StyleMaker(custom_scheme(), window)
    if dialog.exec():
        save_custom_scheme(dialog.scheme)
        window.set_appearance("custom")
        window.appearance_actions["custom"].setChecked(True)
