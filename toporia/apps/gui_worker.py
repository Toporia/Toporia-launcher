# apps/gui_worker.py — headless process for an immutable GUI run snapshot.
# Qt stays in the parent process; numerical work and Matplotlib file rendering
# run here. Newline-delimited JSON carries logs/progress/results over stdout.

import base64
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np

from toporia.apps.gui.project import Project, _atomic_json
from toporia.framework.problem.mesh import projection


class StopRequested(Exception):
    """Cooperative interruption at an iteration or log boundary."""


def execute(project, on_iteration):
    """Dispatch every supported study using plain saved values, never Qt widgets."""
    from toporia.engine.modes.check import check_parts
    from toporia.engine.modes.compare import compare_load_cases, compare_two
    from toporia.engine.modes.methods import compare_methods, sweep_methods
    from toporia.engine.modes.sensitivity import sensitivity_field, sensitivity_sweep, sensitivity_sweep_2d
    from toporia.engine.modes.single import run_one
    from toporia.engine.modes.sweep import sweep, sweep_2d
    from toporia.framework.problem.scenario import LoadCase

    cfg, study = project.run, project.study
    mode = study.get("mode", "Run One")
    callback = {"on_iteration": on_iteration}
    if mode == "Run One":
        store, density = run_one(cfg, **callback)
        path = Path(cfg.output.dir) / "design.npy"
        np.save(path, density)
        return {"kind": "density", "path": str(path), "folder": str(store.output_dir),
                "objectives": store.objectives, "iteration": len(store.objectives)}
    if mode == "Check Parts":
        if not check_parts(cfg):
            raise ValueError("One or more selected parts failed their conformance checks")
        return {"kind": "checks"}
    if mode == "Sweep":
        s = study["sg"]
        sweep(s["param"], s["min_val"], s["max_val"], s["n_rows"], s["n_cols"], cfg, **callback)
        path = Path(cfg.output.dir) / f"sweep_{s['param']}" / "sweep_grid.png"
    elif mode == "Sweep 2D":
        s = study["sg2"]
        sweep_2d(s["row_param"], s["row_min"], s["row_max"], s["n_rows"],
                 s["col_param"], s["col_min"], s["col_max"], s["n_cols"], cfg, **callback)
        path = Path(cfg.output.dir) / f"sweep2d_{s['row_param']}_vs_{s['col_param']}" / "sweep2d_grid.png"
    elif mode == "Compare Two":
        s = study["cg"]
        path, _, _ = compare_two(s["param"], s["value_a"], s["value_b"], cfg, **callback)
    elif mode == "Compare Load Cases":
        s = study["clcg"]
        path, _, _ = compare_load_cases([LoadCase(**v) for v in s["lc_a"]],
                                         [LoadCase(**v) for v in s["lc_b"]], cfg, **callback)
    elif mode == "Compare Methods":
        path, _ = compare_methods(study["cmg"]["selected"], cfg, **callback)
    elif mode == "Sweep Methods":
        s = study["msg"]
        path, _ = sweep_methods(s["selected"], s["param"], s["min_val"], s["max_val"], s["n_values"], cfg, **callback)
    elif mode == "Sensitivity":
        s = study["sens"]
        path, _ = sensitivity_field(s["param"], s["base_value"], s["gap"], cfg, **callback)
    elif mode == "Sensitivity Sweep":
        s = study["ssg"]
        path = sensitivity_sweep(s["sweep_param"], s["min_val"], s["max_val"], s["n_rows"], s["n_cols"],
                                 s["sens_param"], s["base_value"], s["gap"], cfg, **callback)
    elif mode == "Sensitivity Sweep 2D":
        s = study["ssg2"]
        path = sensitivity_sweep_2d(s["row_param"], s["row_min"], s["row_max"], s["n_rows"],
                                    s["col_param"], s["col_min"], s["col_max"], s["n_cols"],
                                    s["sens_param"], s["base_value"], s["gap"], cfg, **callback)
    else:
        raise ValueError(f"Unknown study mode: {mode}")
    if path is None:
        raise ValueError("The study produced no results; inspect the log for incompatible methods")
    return {"kind": "image", "path": str(path)}


def main(path):
    """Execute one snapshot, recording a durable terminal status even on failure."""
    path = Path(path).resolve()
    folder = path.parent
    output = sys.stdout

    def emit(event_type, **values):
        output.write("TOPORIA " + json.dumps({"event": event_type, **values}, allow_nan=False) + "\n")
        output.flush()

    class Logs:
        """Translate engine output without letting plugin prints corrupt the protocol."""
        buffer = ""

        def write(self, text):
            self.buffer += text
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                emit("log", text=line)

        def flush(self):
            if self.buffer:
                emit("log", text=self.buffer)
                self.buffer = ""

    def iteration(density, objectives, number):
        if (folder / "stop.flag").exists():
            raise StopRequested()
        shown = np.ascontiguousarray(projection(density), dtype="float32")
        emit("iteration", shape=shown.shape, density=base64.b64encode(shown.tobytes()).decode("ascii"),
             objectives=objectives, iteration=number)

    status = {"mode": "", "status": "running"}
    sys.stdout = Logs()
    try:
        project = Project.load(path)
        status["mode"] = project.study.get("mode", "Run One")
        _atomic_json(folder / "session.json", status)
        project.run = project.run.with_output_dir(folder)
        if (folder / "stop.flag").exists():
            raise StopRequested()
        result = execute(project, iteration)
        status.update(status="finished", result=result)
        emit("result", **result)
    except StopRequested:
        status["status"] = "stopped"
        emit("stopped")
    except Exception:
        status.update(status="error", error=traceback.format_exc())
        emit("error", text=status["error"])
    finally:
        sys.stdout.flush()
        sys.stdout = output
        status["ended"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(folder / "session.json", status)
    return 1 if status["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
