"""The three packages depend one way: toporia_gui -> toporia_library -> toporia_core, never back.

The core finds the library's parts and presets, and the desktop app, through entry points
(pyproject.toml), so it runs, checks and is tested without either.  Every import is checked,
including those inside functions.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {"toporia_core": ("toporia_library", "toporia_gui"), "toporia_library": ("toporia_gui",)}


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from ((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.lineno, node.module


@pytest.mark.parametrize("package", sorted(FORBIDDEN))
def test_a_package_imports_nothing_above_it(package):
    offending = [f"{path.relative_to(ROOT)}:{line} imports {name}"
                 for path in sorted((ROOT / package).rglob("*.py"))
                 for line, name in _imports(path)
                 if name.split(".")[0] in FORBIDDEN[package]]
    assert offending == [], "\n".join(offending)


def test_the_core_finds_the_library_and_the_app_through_entry_points():
    from importlib.metadata import entry_points

    from toporia_core.framework.problem.presets import problem_names
    from toporia_core.framework.registries import METHODS, MODELS, UPDATERS
    assert {ep.value for ep in entry_points(group="toporia.updaters")} >= {"toporia_library.updaters"}
    assert "oc" in UPDATERS.names() and UPDATERS.source("oc") == "toporia"
    assert "q4" in MODELS.names() and "levelset" in METHODS.names()
    assert "MBB Beam" in problem_names()
    assert [ep.value for ep in entry_points(group="toporia.apps") if ep.name == "gui"] == ["toporia_gui:launch"]
