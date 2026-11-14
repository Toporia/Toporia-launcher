"""A local browser interface for Toporia's optimization engine."""

from __future__ import annotations

import base64
import io
import math
import os
import re
import threading
import traceback
import uuid
import webbrowser
from contextlib import redirect_stdout
from dataclasses import dataclass, field, replace
from pathlib import Path

from toporia.framework.problem.files import from_dict, to_dict
from toporia.framework.problem.run import Output, Run
from toporia.framework.problem.scenario import LoadCase, Scenario
from toporia.framework.problem.solver import Solver

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_RESULTS_ROOT = _PROJECT_ROOT / "results" / "web"
_PARAMETER_PATH = re.compile(r"^[A-Za-z0-9_.\[\]-]+$")
_MAX_GRID_SIDE = 20

MODES = {
    "run_one": "Run One",
    "sweep": "Sweep",
    "sweep_2d": "Sweep 2D",
    "compare_two": "Compare Two",
    "compare_load_cases": "Compare Load Cases",
    "compare_methods": "Compare Methods",
    "sensitivity": "Sensitivity",
    "sensitivity_sweep": "Sensitivity Sweep",
    "sensitivity_sweep_2d": "Sensitivity Sweep 2D",
    "check_parts": "Check Parts",
}

_ARTIFACT_SUFFIXES = {".csv", ".dxf", ".json", ".png", ".stl", ".svg", ".vtk"}


class _JobCancelled(Exception):
    """Raised by an iteration callback after a local user requests cancellation."""


@dataclass
class _Job:
    id: str
    run: Run
    mode: str
    options: dict
    output_dir: Path
    status: str = "queued"
    logs: list[str] = field(default_factory=list)
    iteration: int = 0
    total_iterations: int = 0
    objectives: list[float] = field(default_factory=list)
    density_png: str | None = None
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None
    cancel_requested: threading.Event = field(default_factory=threading.Event)


class _JobOutput:
    """A stdout-compatible stream that appends engine messages to one job."""

    def __init__(self, manager, job):
        self._manager = manager
        self._job = job
        self._buffer = ""

    def write(self, text):
        self._buffer += str(text)
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._manager._append_log(self._job, line)
        return len(text)

    def flush(self):
        if self._buffer:
            self._manager._append_log(self._job, self._buffer)
            self._buffer = ""


class _JobManager:
    """Runs one optimization at a time and stores its live state for browser polling."""

    def __init__(self, output_root):
        self._output_root = Path(output_root)
        self._jobs: dict[str, _Job] = {}
        self._active_id: str | None = None
        self._lock = threading.RLock()

    def start(self, payload):
        run, mode, options = _build_request(payload)
        with self._lock:
            if self._active_id is not None:
                active = self._jobs[self._active_id]
                if active.status in {"queued", "running"}:
                    raise RuntimeError("Another browser job is already running. Stop it or wait for it to finish.")

            job_id = uuid.uuid4().hex
            output_dir = self._output_root / job_id
            output_dir.mkdir(parents=True, exist_ok=False)
            run = replace(run, output=replace(run.output, dir=output_dir))
            job = _Job(
                id=job_id,
                run=run,
                mode=mode,
                options=options,
                output_dir=output_dir,
                total_iterations=run.solver.max_iter,
            )
            self._jobs[job_id] = job
            self._active_id = job_id
            threading.Thread(target=self._execute, args=(job,), daemon=True, name=f"toporia-{job_id[:8]}").start()
            return self.snapshot(job_id)

    def _execute(self, job):
        with self._lock:
            job.status = "running"
        stream = _JobOutput(self, job)
        try:
            import matplotlib

            matplotlib.use("Agg", force=True)
            with redirect_stdout(stream):
                result = _dispatch(job.run, job.mode, job.options, lambda *args: self._on_iteration(job, *args))
                stream.flush()
            job.artifacts = self._find_artifacts(job.output_dir)
            if isinstance(result, bool):
                self._append_log(job, "All selected parts conform." if result else "One or more parts did not conform.")
            with self._lock:
                job.status = "completed"
        except _JobCancelled:
            stream.flush()
            with self._lock:
                job.status = "cancelled"
            self._append_log(job, "Run cancelled.")
        except Exception:
            stream.flush()
            job.error = traceback.format_exc()
            with self._lock:
                job.status = "failed"
            self._append_log(job, job.error.rstrip())
        finally:
            with self._lock:
                if self._active_id == job.id:
                    self._active_id = None

    def _on_iteration(self, job, density, objectives, iteration):
        if job.cancel_requested.is_set():
            raise _JobCancelled()
        import numpy as np
        from PIL import Image

        from toporia.framework.problem.mesh import projection

        material = np.flipud(np.clip(projection(density), 0.0, 1.0))
        pixels = np.zeros((*material.shape, 4), dtype=np.uint8)
        pixels[..., :3] = (207, 207, 200)
        pixels[..., 3] = np.asarray(np.round(material * 255), dtype=np.uint8)
        image = Image.fromarray(pixels)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        with self._lock:
            if iteration <= job.iteration:
                job.objectives = []
            job.iteration = int(iteration)
            job.objectives = [float(value) for value in objectives]
            job.density_png = base64.b64encode(buffer.getvalue()).decode("ascii")

    def _find_artifacts(self, output_dir):
        return sorted(
            path.relative_to(output_dir).as_posix()
            for path in output_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in _ARTIFACT_SUFFIXES
        )

    def _append_log(self, job, line):
        with self._lock:
            job.logs.append(str(line))

    def cancel(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status not in {"queued", "running"} or job.mode == "check_parts":
                return False
            job.cancel_requested.set()
            return True

    def snapshot(self, job_id, after=0):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "id": job.id,
                "status": job.status,
                "mode": job.mode,
                "iteration": job.iteration,
                "total_iterations": job.total_iterations,
                "objectives": list(job.objectives),
                "density_png": job.density_png,
                "logs": job.logs[after:],
                "next_log": len(job.logs),
                "artifacts": list(job.artifacts),
                "error": job.error,
                "cancellable": job.mode != "check_parts" and job.status in {"queued", "running"},
            }

    def file(self, job_id, relative_path):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            root = job.output_dir.resolve()
        requested = (root / relative_path).resolve()
        if root not in requested.parents or not requested.is_file():
            return None
        return requested


def _build_request(payload):
    if not isinstance(payload, dict):
        raise ValueError("The request body must be a JSON object.")
    unknown_request = set(payload) - {"preset", "mode", "scenario", "solver", "output", "options"}
    if unknown_request:
        raise ValueError(f"Unknown request field(s): {sorted(unknown_request)}")
    mode = payload.get("mode")
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}. Available modes: {', '.join(MODES)}")

    preset = payload.get("preset")
    from toporia.plugins.problems import get_run, problem_names

    if preset not in problem_names():
        raise ValueError(f"Unknown preset {preset!r}. Available presets: {', '.join(problem_names())}")
    base = get_run(preset)
    scenario_data = payload.get("scenario", to_dict(base.scenario))
    solver_data = payload.get("solver", to_dict(base.solver))
    if not isinstance(scenario_data, dict) or not isinstance(solver_data, dict):
        raise ValueError("Scenario and solver settings must each be JSON objects.")
    scenario = from_dict(Scenario, scenario_data)
    solver = from_dict(Solver, solver_data)

    output_data = payload.get("output", {})
    if not isinstance(output_data, dict):
        raise ValueError("Output settings must be a JSON object.")
    unknown_output = set(output_data) - {"save_every", "postprocess"}
    if unknown_output:
        raise ValueError(f"Unknown output setting(s): {sorted(unknown_output)}")
    if "save_every" in output_data and (
        isinstance(output_data["save_every"], bool)
        or not isinstance(output_data["save_every"], int)
        or output_data["save_every"] < 0
    ):
        raise ValueError("Output setting 'save_every' must be a non-negative integer.")
    if "postprocess" in output_data and (
        not isinstance(output_data["postprocess"], list)
        or not all(isinstance(item, dict) and isinstance(item.get("type"), str)
                   for item in output_data["postprocess"])
    ):
        raise ValueError("Output setting 'postprocess' must be a list of typed post-processor objects.")
    output = from_dict(Output, output_data)
    options = payload.get("options", {})
    if not isinstance(options, dict):
        raise ValueError("Mode options must be a JSON object.")
    _validate_mode_options(mode, options)
    return Run(scenario=scenario, solver=solver, output=output), mode, options


def _number(options, key, *, positive=False):
    value = options.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Mode option {key!r} must be a finite number.")
    if positive and value <= 0:
        raise ValueError(f"Mode option {key!r} must be greater than zero.")
    return float(value)


def _integer(options, key, *, minimum=1):
    value = options.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"Mode option {key!r} must be an integer greater than or equal to {minimum}.")
    if key in {"n_rows", "n_cols"} and value > _MAX_GRID_SIDE:
        raise ValueError(f"Mode option {key!r} cannot exceed {_MAX_GRID_SIDE}.")
    return value


def _parameter(options, key):
    value = options.get(key)
    if not isinstance(value, str) or not _PARAMETER_PATH.fullmatch(value):
        raise ValueError(f"Mode option {key!r} must be a valid parameter path.")
    return value


def _validate_mode_options(mode, options):
    schemas = {
        "run_one": set(),
        "check_parts": set(),
        "sweep": {"parameter", "min_val", "max_val", "n_rows", "n_cols"},
        "sweep_2d": {"row_param", "row_min", "row_max", "n_rows",
                     "col_param", "col_min", "col_max", "n_cols"},
        "compare_two": {"param_key", "value_a", "value_b"},
        "compare_load_cases": {"load_cases_a", "load_cases_b"},
        "compare_methods": {"methods"},
        "sensitivity": {"param_key", "base_value", "gap"},
        "sensitivity_sweep": {"sweep_param", "min_val", "max_val", "n_rows", "n_cols",
                              "sens_param", "base_value", "gap"},
        "sensitivity_sweep_2d": {"row_param", "row_min", "row_max", "n_rows",
                                 "col_param", "col_min", "col_max", "n_cols",
                                 "sens_param", "base_value", "gap"},
    }
    unknown = set(options) - schemas[mode]
    missing = schemas[mode] - set(options)
    if unknown or missing:
        details = []
        if missing:
            details.append(f"missing {sorted(missing)}")
        if unknown:
            details.append(f"unknown {sorted(unknown)}")
        raise ValueError(f"Invalid options for {mode!r}: {'; '.join(details)}.")

    if mode in {"run_one", "check_parts"}:
        return
    elif mode == "sweep":
        _parameter(options, "parameter")
        _number(options, "min_val")
        _number(options, "max_val")
        _integer(options, "n_rows")
        _integer(options, "n_cols")
    elif mode == "sweep_2d":
        _parameter(options, "row_param")
        _number(options, "row_min")
        _number(options, "row_max")
        _integer(options, "n_rows")
        _parameter(options, "col_param")
        _number(options, "col_min")
        _number(options, "col_max")
        _integer(options, "n_cols")
    elif mode == "compare_two":
        _parameter(options, "param_key")
        _number(options, "value_a")
        _number(options, "value_b")
    elif mode == "compare_load_cases":
        _load_cases(options, "load_cases_a")
        _load_cases(options, "load_cases_b")
    elif mode == "compare_methods":
        methods = options.get("methods")
        if not isinstance(methods, list) or not methods or not all(isinstance(name, str) for name in methods):
            raise ValueError("Mode option 'methods' must be a non-empty list of method names.")
        from toporia.plugins.methods import method_class

        for name in methods:
            method_class(name)
    elif mode == "sensitivity":
        _parameter(options, "param_key")
        _number(options, "base_value")
        _number(options, "gap", positive=True)
    elif mode == "sensitivity_sweep":
        _parameter(options, "sweep_param")
        _number(options, "min_val")
        _number(options, "max_val")
        _integer(options, "n_rows")
        _integer(options, "n_cols")
        _parameter(options, "sens_param")
        _number(options, "base_value")
        _number(options, "gap", positive=True)
    elif mode == "sensitivity_sweep_2d":
        _parameter(options, "row_param")
        _number(options, "row_min")
        _number(options, "row_max")
        _integer(options, "n_rows")
        _parameter(options, "col_param")
        _number(options, "col_min")
        _number(options, "col_max")
        _integer(options, "n_cols")
        _parameter(options, "sens_param")
        _number(options, "base_value")
        _number(options, "gap", positive=True)


def _load_cases(options, key):
    cases = options.get(key)
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"Mode option {key!r} must be a non-empty list of load cases.")
    try:
        return [from_dict(LoadCase, case) for case in cases]
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid load case in {key!r}: {error}") from error


def _dispatch(run, mode, options, on_iteration):
    if mode == "run_one":
        from toporia.engine.modes.single import run_one

        return run_one(run, on_iteration)
    if mode == "check_parts":
        from toporia.engine.modes.check import check_parts

        return check_parts(run)
    if mode == "sweep":
        from toporia.engine.modes.sweep import sweep

        return sweep(
            options["parameter"], options["min_val"], options["max_val"],
            options["n_rows"], options["n_cols"], run, on_iteration,
        )
    if mode == "sweep_2d":
        from toporia.engine.modes.sweep import sweep_2d

        return sweep_2d(
            options["row_param"], options["row_min"], options["row_max"], options["n_rows"],
            options["col_param"], options["col_min"], options["col_max"], options["n_cols"],
            run, on_iteration,
        )
    if mode == "compare_two":
        from toporia.engine.modes.compare import compare_two

        return compare_two(options["param_key"], options["value_a"], options["value_b"], run, on_iteration)
    if mode == "compare_load_cases":
        from toporia.engine.modes.compare import compare_load_cases

        return compare_load_cases(
            _load_cases(options, "load_cases_a"),
            _load_cases(options, "load_cases_b"),
            run,
            on_iteration,
        )
    if mode == "compare_methods":
        from toporia.engine.modes.methods import compare_methods

        return compare_methods(options["methods"], run, on_iteration)
    if mode == "sensitivity":
        from toporia.engine.modes.sensitivity import sensitivity_field

        return sensitivity_field(options["param_key"], options["base_value"], options["gap"], run, on_iteration)
    if mode == "sensitivity_sweep":
        from toporia.engine.modes.sensitivity import sensitivity_sweep

        return sensitivity_sweep(
            options["sweep_param"], options["min_val"], options["max_val"],
            options["n_rows"], options["n_cols"], options["sens_param"],
            options["base_value"], options["gap"], run, on_iteration,
        )
    if mode == "sensitivity_sweep_2d":
        from toporia.engine.modes.sensitivity import sensitivity_sweep_2d

        return sensitivity_sweep_2d(
            options["row_param"], options["row_min"], options["row_max"], options["n_rows"],
            options["col_param"], options["col_min"], options["col_max"], options["n_cols"],
            options["sens_param"], options["base_value"], options["gap"], run, on_iteration,
        )
    raise ValueError(f"Unsupported mode {mode!r}.")


def _param_metadata(param):
    return {
        "name": param.name,
        "label": param.label,
        "kind": param.kind,
        "default": param.default,
        "min": param.min,
        "max": param.max,
        "step": param.step,
        "decimals": param.decimals,
        "choices": param.choices,
        "units": param.units,
        "help": param.help,
    }


def _plugin_metadata(cls, missing_dependencies):
    missing = missing_dependencies(cls)
    info = {
        "name": cls.name,
        "label": cls.label,
        "missing_dependencies": missing,
        "params": [_param_metadata(param) for param in cls.params],
    }
    if hasattr(cls, "capabilities"):
        info["capabilities"] = {
            "dims": getattr(cls.capabilities, "dims", ()),
        }
    return info


def _metadata():
    from toporia.framework import OUTPUT_PARAMS, SCENARIO_PARAMS, SOLVER_PARAMS
    from toporia.framework.parts.composition import ComposedMethod
    from toporia.framework.registry import missing_dependencies
    from toporia.plugins.filters import FILTERS
    from toporia.plugins.interpolations import INTERPOLATIONS
    from toporia.plugins.methods import method_classes
    from toporia.plugins.models import MODELS
    from toporia.plugins.postprocessors import POSTPROCESSORS
    from toporia.plugins.problems import get_run, problem_names
    from toporia.plugins.representations import REPRESENTATIONS
    from toporia.plugins.responses import CONSTRAINT_ROLE, OBJECTIVE_ROLE, responses_for
    from toporia.plugins.schedules import SCHEDULES
    from toporia.plugins.updaters import UPDATERS

    methods = []
    for method in method_classes():
        composed = issubclass(method, ComposedMethod)
        info = _plugin_metadata(method, missing_dependencies)
        info["composed"] = composed
        if composed:
            info["model"] = method.model.name
            info["updater"] = method.updater.name
        info["capabilities"] = {
            "accepts_filters": method.capabilities.accepts_filters,
            "accepts_representation": method.capabilities.accepts_representation,
            "accepts_interpolation": method.capabilities.accepts_interpolation,
            "objectives": method.capabilities.objectives,
            "constraints": method.capabilities.constraints,
            "max_constraints": method.capabilities.max_constraints,
            "dims": method.capabilities.dims,
            "variable_kind": method.capabilities.variable_kind,
        }
        methods.append(info)

    def catalog(classes):
        return [_plugin_metadata(cls, missing_dependencies) for cls in classes]

    presets = []
    for name in problem_names():
        run = get_run(name)
        presets.append({
            "name": name,
            "scenario": to_dict(run.scenario),
            "solver": to_dict(run.solver),
            "output": {"save_every": run.output.save_every, "postprocess": run.output.postprocess},
        })
    return {
        "modes": [{"id": key, "label": value} for key, value in MODES.items()],
        "methods": methods,
        "models": catalog(MODELS.classes()),
        "updaters": catalog(UPDATERS.classes()),
        "filters": catalog(FILTERS.classes()),
        "interpolations": catalog(INTERPOLATIONS.classes()),
        "representations": catalog(REPRESENTATIONS.classes()),
        "objectives": catalog(responses_for(OBJECTIVE_ROLE)),
        "constraints": catalog(responses_for(CONSTRAINT_ROLE)),
        "schedules": catalog(SCHEDULES.classes()),
        "postprocessors": catalog(POSTPROCESSORS.classes()),
        "params": {
            "scenario": [_param_metadata(param) for param in SCENARIO_PARAMS],
            "solver": [_param_metadata(param) for param in SOLVER_PARAMS],
            "output": [_param_metadata(param) for param in OUTPUT_PARAMS],
        },
        "presets": presets,
    }


def create_app(output_root=None):
    """Create the Flask app; kept separate so the API can be tested without opening a browser."""
    from flask import Flask, abort, jsonify, render_template, request, send_file

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    manager = _JobManager(output_root or _RESULTS_ROOT)
    app.extensions["toporia_job_manager"] = manager

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/metadata")
    def metadata():
        return jsonify(_metadata())

    @app.post("/api/describe")
    def describe():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify(error="Request body must be valid JSON."), 400
        if not isinstance(payload, dict):
            return jsonify(error="The request body must be a JSON object."), 400
        try:
            run, _, _ = _build_request({
                "preset": payload.get("preset"),
                "scenario": payload.get("scenario"),
                "solver": payload.get("solver"),
                "output": payload.get("output"),
                "mode": "run_one",
                "options": {},
            })
            from toporia.engine.pipeline import pipeline_notes, pipeline_stages
            from toporia.plugins.catalog import parameter_paths, schedulable_paths

            method = run.solver.method
            setup = {
                "objective": run.scenario.objective,
                "constraints": run.scenario.constraints,
                "interpolation": run.solver.interpolation,
                "representation": run.solver.representation,
            }
            filters = run.solver.filter_specs
            schedules = run.solver.schedules
            paths = parameter_paths(
                method, filters, len(run.scenario.load_cases),
                schedules=schedules, **setup,
            )
            schedulable = schedulable_paths(method, filters, **setup)
            return jsonify(
                stages=pipeline_stages(run),
                notes=pipeline_notes(method, run),
                parameters=[{"label": label, "path": path} for label, path in paths],
                schedulable=[{"label": label, "path": path} for label, path in schedulable],
            )
        except (KeyError, TypeError, ValueError) as error:
            return jsonify(error=str(error)), 400

    @app.post("/api/jobs")
    def start_job():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify(error="Request body must be valid JSON."), 400
        try:
            return jsonify(manager.start(payload)), 202
        except RuntimeError as error:
            return jsonify(error=str(error)), 409
        except (KeyError, TypeError, ValueError) as error:
            return jsonify(error=str(error)), 400

    @app.get("/api/jobs/<job_id>")
    def job_status(job_id):
        try:
            after = int(request.args.get("after", "0"))
        except ValueError:
            return jsonify(error="'after' must be a non-negative integer."), 400
        if after < 0:
            return jsonify(error="'after' must be a non-negative integer."), 400
        snapshot = manager.snapshot(job_id, after)
        if snapshot is None:
            abort(404)
        return jsonify(snapshot)

    @app.post("/api/jobs/<job_id>/cancel")
    def cancel_job(job_id):
        snapshot = manager.snapshot(job_id)
        if snapshot is None:
            abort(404)
        if not manager.cancel(job_id):
            return jsonify(error="This job cannot be cancelled now."), 409
        return jsonify(status="cancellation requested")

    @app.get("/api/jobs/<job_id>/files/<path:relative_path>")
    def job_file(job_id, relative_path):
        path = manager.file(job_id, relative_path)
        if path is None:
            abort(404)
        return send_file(path, as_attachment=True, download_name=path.name)

    return app


def launch():
    """Start the single-user server and open its local browser page."""
    from werkzeug.serving import make_server

    host = os.environ.get("TOPORIA_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("TOPORIA_WEB_PORT", "8765"))
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    open_browser = os.environ.get("TOPORIA_WEB_OPEN_BROWSER", "1").lower() not in {"0", "false", "no"}
    app = create_app()
    server = make_server(host, port, app, threaded=True)
    url = f"http://{browser_host}:{port}/"
    print(f"Toporia browser UI: {url}")
    if open_browser and not webbrowser.open_new_tab(url):
        print("Open the URL above in your browser. Press Ctrl+C here to stop Toporia.")
    server.serve_forever()


__all__ = ["create_app", "launch"]
