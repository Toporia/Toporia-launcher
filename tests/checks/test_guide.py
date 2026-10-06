"""test_guide.py — the examples in docs/writing-plugins.md run, and conform.

Every code block in the guide marked `# example:` is executed here and every
plugin class it defines goes through the conformance test, so the guide can
never drift from the code it describes.
"""

import re
from pathlib import Path

import pytest

from toporia.checks import conformance
from toporia.framework.optimisers.external_loop import ExternalOptimizer
from toporia.framework.parts.updater import Updater

GUIDE = Path(__file__).resolve().parents[2] / "docs" / "writing-plugins.md"
BLOCKS = [block for block in re.findall(r"```python\n(.*?)```", GUIDE.read_text(encoding="utf-8"), re.S)
          if "# example:" in block]


def _plugins(block):
    namespace = {"__name__": "guide_example"}
    exec(compile(block, str(GUIDE), "exec"), namespace)
    return [obj for obj in namespace.values()
            if isinstance(obj, type) and obj.__module__ == "guide_example" and getattr(obj, "name", "")]


def test_the_guide_has_an_example_of_every_kind_it_teaches():
    kinds = [re.search(r"# example: (\w+)", block).group(1) for block in BLOCKS]
    assert kinds == ["updater", "external", "filter", "response"]


@pytest.mark.parametrize("block", BLOCKS, ids=[re.search(r"# example: (\w+)", b).group(1) for b in BLOCKS])
def test_every_guide_example_conforms(block):
    plugins = _plugins(block)
    assert len(plugins) == 1
    plugin = plugins[0]
    # The library example is honest about failing the benchmark (see the guide);
    # here it only has to show that the wrapping itself is correct.
    options = {"benchmark": False} if issubclass(plugin, ExternalOptimizer) else {}
    report = conformance(plugin, **options)
    report.assert_ok()
    if issubclass(plugin, Updater) and not options:
        assert any(c.name.startswith("benchmark") and c.passed for c in report.checks)


def test_the_slsqp_template_the_guide_points_to_is_registered_and_conforms():
    text = GUIDE.read_text(encoding="utf-8")
    assert "library/updaters/scipy_slsqp.py" in text
    conformance("updater:scipy_slsqp").assert_ok()
