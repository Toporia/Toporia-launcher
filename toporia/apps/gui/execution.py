# apps/gui/execution.py — Qt process lifecycle and result ownership for MainWindow.
# Immutable input snapshots and terminal session records make interrupted work
# reviewable. A separate headless process keeps editing/plotting in the Qt thread.

import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np
from PySide6.QtCore import QProcess, QProcessEnvironment
from PySide6.QtWidgets import QMessageBox

from .preflight import problems
from .project import Project, _atomic_json


class ExecutionActions:
    """MainWindow mixin for asynchronous, project-owned runs and results."""

    def start_execution(self):
        """Validate, snapshot and launch the selected study in a headless process."""
        if self._running:
            return
        cfg = self.current_config()
        issues = problems(cfg, check_mesh=True, mesh_limit=None)
        if cfg.scenario.regions is not None and self.mode.currentText() == "Compare Load Cases":
            issues.append("Regional loads own their vectors. Compare Load Cases currently edits legacy shared vectors; use separate projects or cases for regional loads.")
        if issues:
            QMessageBox.warning(self, "Problem needs attention", "\n".join(issues))
            return
        if not self.save_project():
            return
        snapshot = self._capture_project()
        folder = self.project.results_dir / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6])
        try:
            snapshot.save(folder / "input.top")
            _atomic_json(folder / "session.json", {"status": "starting", "mode": self.mode.currentText()})
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot create run", str(error))
            return
        from . import runner
        runner.last_run_folder = None
        self._refresh_export_buttons()
        self._run_folder, self._run_config = folder, cfg
        self._terminal_event = None
        self._stdout_buffer = ""
        self._running, self._stop = True, False
        self.log.clear()
        self.canvas.reset()
        self.go_to_step(2)
        self.run_status.setText("Starting…")
        self.run_progress.setMaximum(cfg.solver.max_iter)
        self.run_progress.setValue(0)
        self._set_execution_controls(False)
        self.run_btn.setText("Stop")
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(Path(__file__).resolve().parents[3]))
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONPATH", str(Path(__file__).resolve().parents[3]))
        environment.insert("MPLBACKEND", "Agg")
        self.process.setProcessEnvironment(environment)
        self.process.readyReadStandardOutput.connect(self._read_worker)
        self.process.readyReadStandardError.connect(self._read_worker_error)
        self.process.finished.connect(self._worker_finished)
        self.process.errorOccurred.connect(self._worker_error)
        executable = Path(sys.executable)
        if executable.name.lower() == "pythonw.exe":
            executable = executable.with_name("python.exe")
        self.process.start(str(executable), ["-u", "-m", "toporia.apps.gui_worker", str(folder / "input.top")])

    def _set_execution_controls(self, enabled):
        """Freeze mutable setup; keep the log, plot and Stop button responsive."""
        self._pages.setEnabled(enabled)
        self.problem_editor.setEnabled(enabled)
        self.method_view.setEnabled(enabled)
        self.notes.setReadOnly(not enabled)
        for action in self.file_actions:
            action.setEnabled(enabled)
        for button in self._step_buttons.buttons():
            button.setEnabled(enabled)
        self._back_btn.setEnabled(enabled and self.current_step() > 0)
        self._next_btn.setEnabled(enabled and self.current_step() < 3)
        self.config_combo.setEnabled(enabled)

    def stop_execution(self):
        """Request a cooperative stop at the next iteration boundary."""
        if self._running:
            self._stop = True
            (self._run_folder / "stop.flag").touch()
            self.run_status.setText("Stop requested · waiting for the current solve")

    def _read_worker(self):
        """Reassemble partial pipe reads before decoding complete protocol messages."""
        self._stdout_buffer += bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            if not line.startswith("TOPORIA "):
                self._log(line)
                continue
            try:
                self._worker_message(json.loads(line[8:]))
            except (ValueError, KeyError, TypeError) as error:
                self._log(f"[Worker message] {error}")

    def _read_worker_error(self):
        """Preserve dependency diagnostics from stderr in the run log."""
        self._log(bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace"))

    def _worker_message(self, message):
        """Apply worker output to Qt-owned plots and execution status."""
        event = message["event"]
        if event == "log":
            self._log(message["text"])
        elif event == "iteration":
            density = np.frombuffer(base64.b64decode(message["density"]), dtype="float32").reshape(message["shape"])
            if message["iteration"] <= self.run_progress.value():
                self.canvas.reset()
            self.canvas.refresh(density, message["objectives"], message["iteration"])
            self.run_progress.setValue(message["iteration"])
            self.run_status.setText(f"Iteration {message['iteration']} · material {density.mean():.1%}")
        elif event in {"result", "stopped", "error"}:
            self._terminal_event = event
            if event == "result":
                self._show_result(message, self._run_config.solver.m)
            elif event == "error":
                self._log(message["text"])

    def _show_result(self, result, resolution):
        """Own only finished single-run results; studies display their result image."""
        from . import runner
        runner.last_run_folder = None
        if result["kind"] == "density":
            density = np.load(result["path"], allow_pickle=False)
            runner.last_run_folder = Path(result["folder"])
            for canvas in (self.canvas, self.post_canvas):
                canvas.reset()
                canvas.refresh(density, result.get("objectives", [0]), result.get("iteration", 0))
                if density.ndim == 3:
                    canvas.show_3d(density, 1 / resolution, self._log)
        elif result["kind"] == "image":
            for canvas in (self.canvas, self.post_canvas):
                canvas.show_grid(result["path"], self.mode.currentText())

    def _worker_error(self, error):
        """Restore controls if the worker could not start at all."""
        if error == QProcess.FailedToStart:
            self._terminal_event = "error"
            self._log(self.process.errorString())
            self._worker_finished(-1)

    def _worker_finished(self, exit_code, _status=None):
        """Leave an unambiguous durable status on completion, stop or process failure."""
        if not self._running:
            return
        self._read_worker()
        status = {"result": "Finished", "stopped": "Stopped", "error": "Failed"}.get(self._terminal_event, "Interrupted")
        if exit_code != 0 and self._terminal_event != "error":
            status = "Interrupted"
        self._running = False
        self._set_execution_controls(True)
        self._show_run_label()
        try:
            session = self._run_folder / "session.json"
            record = json.loads(session.read_text(encoding="utf-8")) if session.exists() else {}
            if status == "Interrupted" or (status == "Failed" and record.get("status") != "error"):
                _atomic_json(session, {"status": "interrupted" if status == "Interrupted" else "error",
                                       "mode": self.mode.currentText(), "error": self.process.errorString()})
            (self._run_folder / "console.txt").write_text(self.log.toPlainText(), encoding="utf-8")
        except (OSError, ValueError) as error:
            self._log(f"Could not persist the final session log: {error}")
        if status == "Finished":
            self.run_progress.setMaximum(100)
            self.run_progress.setValue(100)
        self.run_status.setText(status + " · " + str(self._run_folder))
        self._refresh_export_buttons()
        self._refresh_run_history()
        self.process.deleteLater()

    def _refresh_run_history(self):
        """Discover project-local sessions after reopening without embedding results in .top."""
        self.run_history.clear()
        if self.project.path is None or not self.project.results_dir.exists():
            return
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidgetItem
        for path in sorted(self.project.results_dir.glob("*/session.json"), reverse=True):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                status = record.get("status", "unknown")
                if status in {"running", "starting"}:
                    status = "unfinished"
                item = QListWidgetItem(f"{path.parent.name}\n{record.get('mode', '')} · {status}")
                item.setData(Qt.UserRole, str(path))
                self.run_history.addItem(item)
            except (OSError, ValueError):
                continue

    def _open_history_result(self, item):
        """Review a completed session using its own saved resolution and input snapshot."""
        from PySide6.QtCore import Qt
        if self._running:
            return
        path = Path(item.data(Qt.UserRole))
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            from . import runner
            runner.last_run_folder = None
            self._refresh_export_buttons()
            self.run_status.setText(record.get("status", "unknown") + " · " + str(path.parent))
            log = path.parent / "console.txt"
            if log.exists():
                self.log.setPlainText(log.read_text(encoding="utf-8"))
            if record.get("status") == "finished" and "result" in record:
                snapshot = Project.load(path.parent / "input.top")
                result = dict(record["result"])
                for key in ("path", "folder"):
                    if key in result and not Path(result[key]).is_absolute():
                        result[key] = str(path.parent / result[key])
                self._show_result(result, snapshot.run.solver.m)
                self._refresh_export_buttons()
        except (OSError, ValueError, KeyError) as error:
            QMessageBox.warning(self, "Cannot open result", str(error))
