# apps/gui/project.py — portable project documents, independent of run results.
#
# Project -> readable .top JSON (scenario + solver + output settings + notes).
# ProblemDocument -> readable .pro JSON (scenario + editor objects only).
# Writes replace the destination atomically; a failed save leaves the old file.

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from toporia.framework.problem.files import from_dict, to_dict
from toporia.framework.problem.run import Output, Run
from toporia.framework.problem.scenario import Scenario
from toporia.framework.problem.solver import Solver

FORMAT = 1


def _atomic_json(path, data):
    """Write complete, finite JSON beside the target, then replace it atomically."""
    text = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def _read(path, kind, allowed):
    """Reject unrelated documents and future formats instead of silently losing data."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("kind") != kind:
        raise ValueError(f"Expected a Toporia {kind} document")
    if type(data.get("format")) is not int or data["format"] != FORMAT:
        raise ValueError(f"Unsupported {kind} format: {data.get('format')!r}")
    unknown = set(data) - {"kind", "format", *allowed}
    if unknown:
        raise ValueError(f"Unknown {kind} fields: {sorted(unknown)}")
    return data


@dataclass
class ProblemDocument:
    """A physical definition and its editable scene; None denotes a legacy preset."""

    scenario: Scenario
    objects: list | None = None

    def payload(self):
        """Return the portable definition without solver settings or results."""
        return {"kind": "problem", "format": FORMAT, "scenario": to_dict(self.scenario),
                "objects": self.objects}

    def save(self, path):
        """Export a standalone, human-readable problem document."""
        return _atomic_json(path, self.payload())

    @classmethod
    def load(cls, path):
        """Import a problem, accepting the framework's standalone scenario files too."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("kind") == "scenario":
            from toporia.framework.problem.files import load
            return cls(load(path, "scenario"))
        data = _read(path, "problem", {"scenario", "objects"})
        objects = data.get("objects")
        if objects is not None and not isinstance(objects, list):
            raise ValueError("Problem objects must be a list")
        return cls(from_dict(Scenario, data["scenario"]), objects)


@dataclass
class Project:
    """One configuration, editable notes and study settings; results live on disk."""

    name: str
    run: Run
    benchmark: str | None = None
    objects: list | None = None
    notes: str = ""
    study: dict = field(default_factory=dict)
    view: dict = field(default_factory=dict)
    path: Path | None = field(default=None, compare=False)

    @property
    def problem(self):
        """The independently exportable physical definition."""
        return ProblemDocument(self.run.scenario, self.objects)

    @property
    def results_dir(self):
        """Resolve output relative to the project, never relative to another checkout."""
        if self.path is None:
            raise ValueError("Save the project before creating a results directory")
        return self.path.parent / "results"

    def payload(self):
        """Serialize configuration and UI state, excluding paths and computed results."""
        return {"kind": "project", "format": FORMAT, "name": self.name,
                "scenario": to_dict(self.run.scenario), "solver": to_dict(self.run.solver),
                "output": {"save_every": self.run.output.save_every,
                           "postprocess": self.run.output.postprocess},
                "benchmark": self.benchmark, "objects": self.objects, "notes": self.notes,
                "study": self.study, "view": self.view}

    def save(self, path=None):
        """Save atomically and remember the location only after a successful write."""
        destination = Path(path) if path is not None else self.path
        if destination is None:
            raise ValueError("A project filename is required")
        _atomic_json(destination, self.payload())
        self.path = destination.resolve()
        return self.path

    @classmethod
    def load(cls, path):
        """Recreate all settings; execution output is redirected beside the project."""
        data = _read(path, "project", {"name", "scenario", "solver", "output", "benchmark", "objects",
                                       "notes", "study", "view"})
        for key, default, expected in (("name", "Untitled", str), ("notes", "", str),
                                       ("study", {}, dict), ("view", {}, dict), ("output", {}, dict)):
            if not isinstance(data.get(key, default), expected):
                raise ValueError(f"Project {key} must be {expected.__name__}")
        objects = data.get("objects")
        if objects is not None and not isinstance(objects, list):
            raise ValueError("Project objects must be a list")
        path = Path(path).resolve()
        output = data.get("output", {})
        if set(output) - {"save_every", "postprocess"}:
            raise ValueError("Project output contains unknown settings")
        run = Run(scenario=from_dict(Scenario, data["scenario"]), solver=from_dict(Solver, data["solver"]),
                  output=Output(dir=path.parent / "results", **output))
        return cls(name=data.get("name", path.stem), run=run, benchmark=data.get("benchmark"),
                   objects=objects, notes=data.get("notes", ""), study=data.get("study", {}),
                   view=data.get("view", {}), path=path)
