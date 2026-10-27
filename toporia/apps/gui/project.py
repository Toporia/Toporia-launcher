# apps/gui/project.py — portable project documents, independent of run results.
#
# Project -> readable .top JSON (scenario + solver + output settings + notes).
# ProblemDocument -> readable .pro JSON (scenario + editor objects only).
# Writes replace the destination atomically; a failed save leaves the old file.

import json
import math
import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path

from toporia.framework.problem.files import from_dict, to_dict
from toporia.framework.problem.run import Output, Run
from toporia.framework.problem.scenario import Scenario
from toporia.framework.problem.solver import Solver

FORMAT = 1


def _validate_objects(objects):
    """Validate file structure before handing imported objects to graphics widgets."""
    if objects is None:
        return
    if not isinstance(objects, list):
        raise ValueError("Problem objects must be a list")
    identities = set()
    for obj in objects:
        if not isinstance(obj, dict) or not isinstance(obj.get("id"), str) or obj["id"] in identities:
            raise ValueError("Every object needs a unique string id")
        identities.add(obj["id"])
        if not isinstance(obj.get("name"), str) or obj.get("shape") not in {"point", "line", "rectangle", "circle", "polygon", "box", "sphere", "cylinder", "stl"}:
            raise ValueError("Object name or shape is invalid")
        if obj.get("role") not in {"support", "load", "solid", "void", "domain"}:
            raise ValueError("Unknown object role")
        for key in ("position", "size", "rotation", "force"):
            value = obj.get(key)
            if not isinstance(value, list) or len(value) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in value):
                raise ValueError(f"Object {key} must contain three finite numbers")
        if not isinstance(obj.get("axes"), list) or set(obj["axes"]) - set("xyz"):
            raise ValueError("Object displacement axes are invalid")
        if type(obj.get("case")) is not int or obj["case"] < 0:
            raise ValueError("Object load case must be a nonnegative integer")
        for key in ("extrusion", "inner_radius"):
            if key in obj and (not isinstance(obj[key], (int, float)) or not math.isfinite(obj[key]) or obj[key] < 0):
                raise ValueError(f"Object {key} must be a finite nonnegative number")
        if obj["shape"] == "polygon":
            vertices = obj.get("vertices")
            if not isinstance(vertices, list) or len(vertices) < 3 or any(
                not isinstance(p, list) or len(p) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in p)
                for p in vertices
            ):
                raise ValueError("Polygon vertices must be finite XY pairs")
        if obj["shape"] == "stl":
            from toporia.framework.problem.spatial import triangle_mesh
            triangle_mesh(obj)


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

    def __post_init__(self):
        """Keep the visible scene and the independently runnable scenario consistent."""
        if self.objects is None:
            self.objects = self.scenario.regions
        if self.objects is not None:
            self.scenario = replace(self.scenario, regions=self.objects)

    def payload(self):
        """Return the portable definition without solver settings or results."""
        scenario = replace(self.scenario, regions=None) if self.objects is not None else self.scenario
        return deepcopy({"kind": "problem", "format": FORMAT, "scenario": to_dict(scenario),
                         "objects": self.objects})

    def save(self, path):
        """Export a standalone, human-readable problem document."""
        return _atomic_json(path, self.payload())

    @classmethod
    def load(cls, path):
        """Import a problem, accepting the framework's standalone scenario files too."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("kind") == "scenario":
            from toporia.framework.problem.files import load
            scenario = load(path, "scenario")
            _validate_objects(scenario.regions)
            return cls(scenario)
        data = _read(path, "problem", {"scenario", "objects"})
        objects = data.get("objects", data["scenario"].get("regions"))
        if objects is None:
            objects = data["scenario"].get("regions")
        _validate_objects(objects)
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
    # Execution structure is configuration, separate from presentation state.
    workflow: dict | None = None

    def __post_init__(self):
        """The editor objects are authoritative inputs, including for headless workers."""
        if self.objects is None:
            self.objects = self.run.scenario.regions
        if self.objects is not None:
            self.run = replace(self.run, scenario=replace(self.run.scenario, regions=self.objects))

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

    def payload(self, include_geometry=True):
        """Serialize configuration and UI state, excluding paths and computed results."""
        # Store editor geometry once; __post_init__ compiles it into the Scenario
        # for both the GUI and headless worker. Older files with regions still load.
        scenario = replace(self.run.scenario, regions=None) if self.objects is not None or not include_geometry else self.run.scenario
        data = {"kind": "project", "format": FORMAT, "name": self.name,
                "scenario": to_dict(scenario), "solver": to_dict(self.run.solver),
                "output": {"save_every": self.run.output.save_every,
                           "postprocess": self.run.output.postprocess},
                "benchmark": self.benchmark, "objects": self.objects if include_geometry else None, "notes": self.notes,
                "study": self.study, "view": self.view}
        if self.workflow is not None:
            data["workflow"] = self.workflow
        return deepcopy(data)

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
                                       "notes", "study", "view", "workflow"})
        for key, default, expected in (("name", "Untitled", str), ("notes", "", str),
                                       ("study", {}, dict), ("view", {}, dict), ("output", {}, dict)):
            if not isinstance(data.get(key, default), expected):
                raise ValueError(f"Project {key} must be {expected.__name__}")
        if data.get("benchmark") is not None and not isinstance(data["benchmark"], str):
            raise ValueError("Benchmark must be a name or null")
        study, view = data.get("study", {}), data.get("view", {})
        if "display" in view:
            from .display_options import validate_display
            validate_display(view["display"])
        # Preserve early development snapshots that placed the execution tree
        # in view state; all new saves give it a dedicated configuration field.
        if data.get("workflow") is not None and view.get("workflow") is not None and data["workflow"] != view["workflow"]:
            raise ValueError("Conflicting workflow definitions in configuration and legacy view state")
        workflow = data.get("workflow") if data.get("workflow") is not None else view.get("workflow")
        if workflow is not None:
            from toporia.framework.problem.workflow import nodes, validate_workflow
            validate_workflow(workflow)
            if "active_stage" in view and (not isinstance(view["active_stage"], str) or view["active_stage"] not in {node["id"] for node in nodes(workflow) if node["kind"] == "optimization"}):
                raise ValueError("Active stage must name an optimization function in the workflow")
            view = {key: value for key, value in view.items() if key != "workflow"}
        if "blank_setup" in view:
            setup = view["blank_setup"]
            limits = {"Lx": (0, 10000), "Ly": (0, 10000), "Lz": (0, 10000),
                      "element_size": (0, 1000), "E0": (0, 1e7), "nu": (-.99, .499), "volfrac": (0, 1)}
            choices = {"dimension", "representation", "physics", "objective"}
            if not isinstance(setup, dict) or set(setup) - (choices | limits.keys()):
                raise ValueError("Blank setup must contain supported initial settings")
            if setup.get("dimension") is not None and (type(setup["dimension"]) is not int or setup["dimension"] not in (2, 3)):
                raise ValueError("Blank setup dimension must be 2, 3 or null")
            if any(setup.get(key) is not None and not isinstance(setup[key], str) for key in choices - {"dimension"}):
                raise ValueError("Blank setup choices must be names or null")
            for key, (lower, upper) in limits.items():
                if key in setup and (type(setup[key]) not in (int, float) or not math.isfinite(setup[key]) or not lower <= setup[key] <= upper):
                    raise ValueError(f"Blank setup {key} is outside its supported range")
        if not isinstance(study.get("mode", "Run One"), str) or any(not isinstance(v, dict) for k, v in study.items() if k != "mode"):
            raise ValueError("Study groups must be dictionaries and mode must be text")
        positions = view.get("method_positions", {})
        if not isinstance(positions, dict) or any(not isinstance(v, list) or len(v) != 2 or
            not all(isinstance(n, (int, float)) and math.isfinite(n) for n in v) for v in positions.values()):
            raise ValueError("Diagram positions must contain finite XY pairs")
        camera = view.get("camera3d")
        if camera is not None and (not isinstance(camera, list) or len(camera) != 3 or any(
            not isinstance(v, list) or len(v) != 3 or not all(isinstance(n, (int, float)) and math.isfinite(n) for n in v) for v in camera)):
            raise ValueError("Camera position must contain three finite XYZ vectors")
        objects = data.get("objects", data["scenario"].get("regions"))
        if objects is None:
            objects = data["scenario"].get("regions")
        _validate_objects(objects)
        path = Path(path).resolve()
        output = data.get("output", {})
        if set(output) - {"save_every", "postprocess"}:
            raise ValueError("Project output contains unknown settings")
        run = Run(scenario=from_dict(Scenario, data["scenario"]), solver=from_dict(Solver, data["solver"]),
                  output=Output(dir=path.parent / "results", **output))
        return cls(name=data.get("name", path.stem), run=run, benchmark=data.get("benchmark"),
                   objects=objects, notes=data.get("notes", ""), study=data.get("study", {}),
                   view=view, path=path, workflow=workflow)
