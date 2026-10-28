"""Scientific preset help must contain real images and preserve legacy topics."""

import os
import re
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl
from PySide6.QtGui import QPixmap, QTextDocument
from PySide6.QtWidgets import QApplication, QTextBrowser

from toporia.apps.gui.help import problem_topic
from toporia.apps.research_render import description_html
from toporia.plugins.problems import problem_description, problem_info, problem_names


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("name", [name for name in problem_names() if problem_description(name) is not None])
def test_qt_loads_every_typeset_equation_without_network_or_tex(app, name):
    description = problem_description(name)
    topic = problem_topic(name)
    assert topic.section("What it is") == problem_info(name)[0]
    browser = QTextBrowser()
    markup = topic.to_html()
    browser.setHtml(markup)
    sources = re.findall(r'<img src="([^"]+)"', markup)
    assert len(sources) == len(description.equations)
    for source in sources:
        resource = browser.document().resource(QTextDocument.ImageResource, QUrl(source))
        image = resource.toImage() if isinstance(resource, QPixmap) else resource
        assert image is not None
        assert not image.isNull(), "Qt must display an actual equation, not a broken image"
        assert image.width() > 10 and image.height() > 10
    text = browser.toPlainText()
    assert "Symbols and units" in text
    assert "Limitations" in text
    assert r"\frac" not in text


def test_contributor_text_is_escaped(app):
    description = problem_description("Paper: top88 Fig. 3(a) - Density")
    markup = description_html(replace(description, question='<img src="https://example.invalid/tracker">'))
    assert '&lt;img src=' in markup
    assert '<img src="https://example.invalid/tracker">' not in markup


def test_existing_preset_help_stays_compatible(app):
    name = "MBB Beam"
    assert problem_description(name) is not None
    topic = problem_topic(name)
    assert topic.section("What it is") == problem_info(name)[0]
    assert topic.section("Where it is from") == problem_info(name)[1]
