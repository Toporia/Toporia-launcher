"""framework/ is the core: it imports nothing from the engine, the plugins or the apps."""

import ast
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parents[2] / "toporia" / "framework"
FORBIDDEN = ("toporia.engine", "toporia.plugins", "toporia.apps")


def test_framework_imports_only_itself_and_libraries():
    found = []
    for path in FRAMEWORK.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            found += [f"{path.relative_to(FRAMEWORK)}: {n}" for n in names if n.startswith(FORBIDDEN)]
    assert not found, found
