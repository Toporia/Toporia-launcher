# apps/gui/help.py — the "?" next to every option, and the window it opens.
#
# Every option in the GUI has a small "?" button.  Clicking it opens one
# help window (reused, so the screen does not fill with them) that says what
# the option is, where it comes from or what inspired it, and its details:
#
#   ┌ Help — Density filter ─────────────────────────────┐
#   │ Density filter                                     │
#   │ What it is        Weighted-average spatial filter… │
#   │ Where it is from  Bruns & Tortorelli 2001; …       │
#   │ Parameters        Radius [el] …                    │
#   └────────────────────────────────────────────────────┘
#
# A topic is a plain HelpTopic, built from what the option already declares:
# a Param (help, units, range, source), a plugin class (docstring, reference,
# dependencies, params), or a few sentences written next to the widget.  So a
# new plugin gets its help window by declaring `reference`, with no GUI change.

import html
import inspect
import re
from dataclasses import dataclass, field

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QTextBrowser, QToolButton, QVBoxLayout, QWidget

#: Shown when an option does not say where it comes from.
UNSTATED = "Not stated."


@dataclass
class HelpTopic:
    """What one help window shows: a title, then (heading, text) sections in order."""

    title: str
    sections: list = field(default_factory=list)

    def add(self, heading, text):
        """Append a section; empty text is skipped."""
        if text:
            self.sections.append((heading, str(text)))
        return self

    def section(self, heading):
        """The text under `heading`, or "" when there is none."""
        return next((text for h, text in self.sections if h == heading), "")

    def to_html(self):
        """The topic as rich text, with web addresses made clickable."""
        rows = [f"<h3>{html.escape(self.title)}</h3>"]
        for heading, text in self.sections:
            body = _linkify(html.escape(text)).replace("\n", "<br>")
            rows.append(f"<p><b>{html.escape(heading)}</b><br>{body}</p>")
        return "\n".join(rows)


def _linkify(escaped):
    return re.sub(r"(https?://[^\s<;,)]+)", r'<a href="\1">\1</a>', escaped)


# ── Topics ────────────────────────────────────────────────────────────────────


def text_topic(title, what, source=""):
    """A topic for an option that is not a Param or a plugin: what it is, and where it is from."""
    return HelpTopic(title).add("What it is", what).add("Where it is from", source or "Toporia's own.")


def param_topic(param, owner=None):
    """A topic for one Param; without a source of its own, it inherits its plugin's reference."""
    title = f"{param.label} [{param.units}]" if param.units else param.label
    topic = HelpTopic(title).add("What it is", param.help or UNSTATED)
    if param.source:
        topic.add("Where it is from", param.source)
    elif owner is not None:
        reference = getattr(owner, "reference", "") or UNSTATED
        topic.add("Where it is from", f"A setting of {owner.label}, which comes from: {reference}")
    else:
        topic.add("Where it is from", UNSTATED)
    return topic.add("Details", _param_details(param))


def _param_details(param):
    lines = [f"Name in configs: {param.name}", f"Default: {_shown(param, param.default)}"]
    if param.kind == "choice":
        lines.append("Choices: " + ", ".join(label for _, label in param.choices))
    elif param.is_numeric:
        low = "-∞" if param.min is None else f"{param.min:g}"
        high = "∞" if param.max is None else f"{param.max:g}"
        lines.append(f"Range: {low} to {high}")
    return "\n".join(lines)


def _shown(param, value):
    if param.kind == "choice":
        return next((label for v, label in param.choices if v == value), str(value))
    return f"{value:g}" if isinstance(value, float) else str(value)


def plugin_topic(cls, kind=""):
    """A topic for a plugin class: its docstring, its reference, what it needs, its parameters."""
    from toporia.framework.registry import install_hint, missing_dependencies

    title = f"{cls.label}" + (f"  ({kind})" if kind else "")
    topic = HelpTopic(title)
    topic.add("What it is", inspect.getdoc(cls) or UNSTATED)
    assembled = getattr(cls, "model", None) is not None
    fallback = "Toporia assembles it from the two parts below; each says where it comes from." if assembled else UNSTATED
    topic.add("Where it is from", getattr(cls, "reference", "") or fallback)
    for part in ("model", "updater"):   # a method assembled from parts: both parts' sources
        sub = getattr(cls, part, None)
        if sub is not None:
            topic.add(f"{part.capitalize()}: {sub.label}", getattr(sub, "reference", "") or UNSTATED)
    needs = list(getattr(cls, "dependencies", ()))
    missing = missing_dependencies(cls)
    if needs:
        state = f"not installed here - {install_hint(missing)}" if missing else "installed"
        topic.add("Needs", f"{', '.join(needs)} ({state})")
    params = getattr(cls, "params", ())
    if params:
        topic.add("Parameters", "\n".join(f"{p.label}: {p.help}" for p in params))
    return topic.add("Name in configs", getattr(cls, "name", ""))


def problem_topic(name):
    """A topic for a preset problem."""
    from toporia.plugins.problems import problem_description, problem_info

    about, reference = problem_info(name)
    topic = text_topic(f"Preset: {name}", about or UNSTATED, reference or UNSTATED)
    description = problem_description(name)
    if description is not None:
        from .research_help import ResearchHelpTopic
        return ResearchHelpTopic(topic, description)
    return topic


# ── Window and button ─────────────────────────────────────────────────────────


class HelpWindow(QDialog):
    """The one help window: it stays open beside the main window and shows the last topic asked for."""

    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool)
        self.setWindowTitle("Help")
        self.resize(520, 440)
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        layout.addWidget(self.browser)
        self.topic = None

    @classmethod
    def instance(cls, parent=None):
        """The shared window, created on first use."""
        if cls._instance is None:
            cls._instance = HelpWindow(parent)
        return cls._instance

    def show_topic(self, topic):
        """Show `topic` and bring the window to the front."""
        self.topic = topic
        self.setWindowTitle(f"Help — {topic.title}")
        self.browser.setHtml(topic.to_html())
        self.show()
        self.raise_()


class HelpButton(QToolButton):
    """A small "?" that opens the help window on the topic `provider()` gives at click time.

    `provider` is called when clicked, so a button beside a dropdown explains
    whatever is selected then.  With a `target`, the button hides and shows
    together with it, so a hidden option never leaves a stray "?" behind.
    """

    def __init__(self, provider, target=None, parent=None):
        super().__init__(parent)
        self._provider = provider
        self.setText("?")
        self.setFixedSize(20, 20)
        self.setAutoRaise(True)
        self.setToolTip("What is this, and where does it come from?")
        self.setStyleSheet("QToolButton { border: 1px solid palette(mid); border-radius: 10px; font-weight: bold; }")
        self.clicked.connect(self.open_help)
        if target is not None:
            self._follower = _VisibilityFollower(target, self)

    def topic(self):
        """The topic this button would show now."""
        return self._provider()

    def open_help(self):
        """Open the help window on this button's topic."""
        HelpWindow.instance(self.window()).show_topic(self.topic())


class _VisibilityFollower(QObject):
    """Hide and show `follower` whenever `target` is explicitly hidden or shown."""

    def __init__(self, target, follower):
        super().__init__(follower)
        self._follower = follower
        target.installEventFilter(self)
        if target.isHidden():
            follower.hide()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.ShowToParent:
            self._follower.show()
        elif event.type() == QEvent.HideToParent:
            self._follower.hide()
        return False


def with_help(widget, provider):
    """`widget` with a "?" beside it, in one widget that can go wherever `widget` would."""
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    row.addWidget(widget, 1)
    box.help_button = HelpButton(provider, target=widget)
    row.addWidget(box.help_button)
    return box
