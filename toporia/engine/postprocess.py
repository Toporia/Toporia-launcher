# engine/postprocess.py — apply the run's post-processors to its final design.
#
#   run_postprocessors   after a run: each entry of run.output.postprocess, in
#                        order, on the final design; files go to <run>/post/
#   postprocess_folder   the same on a run saved earlier (toporia post <folder>),
#                        without optimising again
#   check_postprocess    refuse unknown post-processors and parameters before
#                        a run starts, like every other part
#   table_metrics        the numbers a comparison shows, as "threshold.compliance"
#
# A post-processor that fails is reported, and the run and the other
# post-processors are kept: a missing export must not cost an optimisation.

import csv
import json
from pathlib import Path

import numpy as np

from toporia.framework.params import resolve_params
from toporia.framework.parts.postprocess import Result

#: The folder, inside a run's output folder, that post-processors write to.
FOLDER = "post"


def _classes():
    from toporia.plugins.postprocessors import POSTPROCESSORS
    return POSTPROCESSORS


def _instances(specs):
    """[(key, class, instance)] for the specs, parameters validated; keys unique ("threshold", "threshold_2")."""
    found, made, seen = _classes(), [], {}
    for spec in specs:
        spec = dict(spec)
        cls = found.get(spec.pop("type"))
        seen[cls.name] = seen.get(cls.name, 0) + 1
        key = cls.name if seen[cls.name] == 1 else f"{cls.name}_{seen[cls.name]}"
        made.append((key, cls, cls(**resolve_params(f"post-processor {cls.name!r}", cls.params, spec))))
    return made


def check_postprocess(run):
    """Raise before a run if a post-processor is unknown, misconfigured, or needs a missing package."""
    from toporia.framework.registry import install_hint, missing_dependencies
    for _, cls, _ in _instances(run.output.postprocess):
        missing = missing_dependencies(cls)
        if missing:
            raise ImportError(f"Post-processor {cls.name!r} needs {', '.join(missing)}: {install_hint(missing)}")


def run_postprocessors(run, density, folder, geometry=None, problem=None):
    """Apply run.output.postprocess to `density`; return {key: {"type", "metrics", "files"} or {"type", "error"}}."""
    specs = run.output.postprocess
    if not specs:
        return {}
    if problem is None:
        from toporia.framework.problem.mesh import RectangularProblem
        problem = RectangularProblem(run.scenario, run.solver.m)
    folder = Path(folder)
    result = Result(density=np.asarray(density, dtype=float), problem=problem, run=run,
                    folder=folder / FOLDER, geometry=geometry)
    done = {}
    for key, cls, processor in _instances(specs):
        written = len(result.files)
        try:
            metrics = {name: _plain(value) for name, value in processor.process(result).items()}
        except Exception as error:          # one failing export must not cost the run
            done[key] = {"type": cls.name, "error": f"{type(error).__name__}: {error}"}
            print(f"  post {cls.label}: FAILED ({done[key]['error']})")
            continue
        files = [path.relative_to(folder).as_posix() for path in result.files[written:]]
        done[key] = {"type": cls.name, "metrics": metrics, "files": files}
        shown = ", ".join(f"{name}={_shown(value)}" for name, value in metrics.items())
        print(f"  post {cls.label}: {shown}" + (f"  -> {', '.join(files)}" if files else ""))
    return done


def table_metrics(postprocess):
    """The post-processors' numbers worth a column in a comparison, as {"threshold.compliance": value}."""
    found = _classes()
    columns = {}
    for key, entry in postprocess.items():
        cls = found.get(entry["type"]) if entry["type"] in found else None
        wanted = getattr(cls, "table_metrics", None)
        for name, value in entry.get("metrics", {}).items():
            if wanted is None or name in wanted:
                columns[f"{key}.{name}"] = value
    return columns


def postprocess_folder(folder, specs):
    """Post-process a run saved in `folder` (its run.json and final_density.csv) and add the results to run.json."""
    from dataclasses import replace

    from toporia.framework.problem.files import from_dict
    from toporia.framework.problem.run import Run
    from toporia.framework.problem.scenario import Scenario
    from toporia.framework.problem.solver import Solver
    folder = Path(folder)
    record = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    run = Run(scenario=from_dict(Scenario, record["scenario"]["definition"]),
              solver=from_dict(Solver, record["solver"]["definition"])).with_output_dir(folder)
    run = replace(run, output=replace(run.output, postprocess=list(specs)))
    check_postprocess(run)
    density = load_density(folder / "final_density.csv")
    geometry_file = folder / "final_geometry.json"
    geometry = None
    if geometry_file.exists():
        geometry = [np.asarray(p) for p in json.loads(geometry_file.read_text(encoding="utf-8"))["polygons"]]
    done = run_postprocessors(run, density, folder, geometry)
    record["postprocess"] = {**record.get("postprocess", {}), **done}
    (folder / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return done


def load_density(path):
    """The density saved in final_density.csv (two header rows, image orientation), row 0 at y = 0 again."""
    with open(path, newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))[2:]
    return np.flipud(np.array([[float(v) for v in row] for row in rows]))


def save_geometry(folder, geometry):
    """final_geometry.json: the design's explicit outlines, for export later."""
    data = {"units": "mm", "polygons": [np.asarray(p, dtype=float).round(6).tolist() for p in geometry]}
    (Path(folder) / "final_geometry.json").write_text(json.dumps(data) + "\n", encoding="utf-8")


def _plain(value):
    """A metric as plain JSON: numbers as float or int, numpy scalars unwrapped, None kept."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    return float(value)


def _shown(value):
    return f"{value:.4g}" if isinstance(value, float) else str(value)
