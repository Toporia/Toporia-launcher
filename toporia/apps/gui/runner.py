# apps/gui/runner.py — bridge between the GUI and the optimisation scripts
#
# This is the only file in the gui/ package that RUNS optimisation code.  The
# widgets import plugin declarations (Param lists, capabilities) to build
# themselves, but never start a computation.
#
# Responsibilities:
#   1. Redirect print() output from the optimisation scripts into the GUI log box
#   2. Call the real optimisation functions with the live-update callback

import sys
from pathlib import Path

from toporia.engine.modes.check import check_parts as _check_parts
from toporia.engine.modes.compare import compare_load_cases as _compare_lc
from toporia.engine.modes.compare import compare_two as _compare_two
from toporia.engine.modes.sensitivity import sensitivity_field as _sensitivity_field
from toporia.engine.modes.sensitivity import sensitivity_sweep as _sens_sweep
from toporia.engine.modes.sensitivity import sensitivity_sweep_2d as _sens_sweep_2d
from toporia.engine.modes.single import run_one as _run_one
from toporia.engine.modes.sweep import sweep as _sweep
from toporia.engine.modes.sweep import sweep_2d as _sweep_2d

from .config import build_config  # noqa: F401  (re-exported: callers use runner.build_config)


class _LogStream:
    """A file-like object that captures print() output line by line.

    Python's print() writes to sys.stdout.  By swapping sys.stdout with an
    instance of this class, all print calls from the optimisation scripts are
    intercepted and forwarded to the GUI's log text box via the fn callback.
    """
    def __init__(self, fn):
        self._fn  = fn    # the GUI callback: takes a string, appends it to the log
        self._buf = ""    # partial line buffer (print may not always end with \n)

    def write(self, text):
        """Collect text; hand every complete line to the log."""
        self._buf += text
        # A single print() may arrive in multiple write() calls.
        # Accumulate until we see a newline, then fire the callback with the full line.
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)  # split at first newline only
            self._fn(line)

    def flush(self):
        """Hand over whatever is left of an unfinished line."""
        # Called by Python when it wants to ensure all output is delivered.
        if self._buf:
            self._fn(self._buf); self._buf = ""


def run_check(config, log_fn):
    """The Check Parts mode; returns True when every part conforms."""
    old = _redir(log_fn)
    try:
        return _check_parts(config)
    finally:
        sys.stdout = old


def _redir(log_fn):
    """Swap sys.stdout for a _LogStream and return the original stdout."""
    old = sys.stdout
    sys.stdout = _LogStream(log_fn)
    return old   # caller must restore this in a finally block


# ── The three public run functions ────────────────────────────────────────────
# Each one: redirects stdout → calls the real optimisation function → restores stdout.
# The "finally" block guarantees stdout is restored even if an exception occurs.

def run_one(config, on_iter, log_fn):
    """The Run One mode, with its printed output routed to the GUI's log."""
    old = _redir(log_fn)
    try:
        _run_one(config, on_iteration=on_iter)
    finally:
        sys.stdout = old


def run_sweep(config, sg, on_iter, log_fn):
    """sg = SweepParamsGroup widget.  Returns path to the assembled grid PNG."""
    old = _redir(log_fn)
    try:
        _sweep(sg.key(), sg.min_val.value(), sg.max_val.value(),
               sg.n_rows.value(), sg.n_cols.value(), config,
               on_iteration=on_iter)
    finally:
        sys.stdout = old
    # The grid PNG is always written to this predictable location by sweep.py.
    return Path(config.output.dir) / f"sweep_{sg.key()}" / "sweep_grid.png"


def run_sensitivity(config, sg, on_iter, log_fn):
    """sg = SensitivityParamsGroup widget.  Returns path to the sensitivity PNG."""
    old = _redir(log_fn)
    try:
        img_path, _ = _sensitivity_field(
            sg.key(), sg.base_value.value(), sg.gap.value(),
            config, on_iteration=on_iter,
        )
    finally:
        sys.stdout = old
    return img_path


def run_compare_load_cases(config, clcg, on_iter, log_fn):
    """clcg = CompareLoadCasesParamsGroup widget.  Returns path to the comparison PNG."""
    old = _redir(log_fn)
    try:
        img_path, _, _ = _compare_lc(
            clcg.get_load_cases_a(),
            clcg.get_load_cases_b(),
            config,
            on_iteration=on_iter,
        )
    finally:
        sys.stdout = old
    return img_path


def run_compare_two(config, cg, on_iter, log_fn):
    """cg = CompareTwoParamsGroup widget.  Returns path to the comparison PNG."""
    old = _redir(log_fn)
    try:
        img_path, _, _ = _compare_two(
            cg.key(), cg.value_a.value(), cg.value_b.value(),
            config, on_iteration=on_iter,
        )
    finally:
        sys.stdout = old
    return img_path


def run_sensitivity_sweep(config, ssg, on_iter, log_fn):
    """ssg = SensitivitySweepParamsGroup widget.  Returns path to the grid PNG."""
    old = _redir(log_fn)
    try:
        grid_path = _sens_sweep(
            ssg.sweep_key(), ssg.min_val.value(), ssg.max_val.value(),
            ssg.n_rows.value(), ssg.n_cols.value(),
            ssg.sens_key(), ssg.base_value.value(), ssg.gap.value(),
            config, on_iteration=on_iter,
        )
    finally:
        sys.stdout = old
    return grid_path


def run_sensitivity_sweep_2d(config, ssg2, on_iter, log_fn):
    """ssg2 = SensitivitySweep2DParamsGroup widget.  Returns path to the grid PNG."""
    old = _redir(log_fn)
    try:
        grid_path = _sens_sweep_2d(
            ssg2.row_sweep_key(), ssg2.row_min.value(), ssg2.row_max.value(), ssg2.n_rows.value(),
            ssg2.col_sweep_key(), ssg2.col_min.value(), ssg2.col_max.value(), ssg2.n_cols.value(),
            ssg2.sens_key(), ssg2.base_value.value(), ssg2.gap.value(),
            config, on_iteration=on_iter,
        )
    finally:
        sys.stdout = old
    return grid_path


def run_sweep_2d(config, sg, on_iter, log_fn):
    """sg = Sweep2DParamsGroup widget.  Returns path to the assembled grid PNG."""
    old = _redir(log_fn)
    try:
        _sweep_2d(sg.row_key(), sg.row_min.value(), sg.row_max.value(), sg.n_rows.value(),
                  sg.col_key(), sg.col_min.value(), sg.col_max.value(), sg.n_cols.value(),
                  config, on_iteration=on_iter)
    finally:
        sys.stdout = old
    return (Path(config.output.dir)
            / f"sweep2d_{sg.row_key()}_vs_{sg.col_key()}"
            / "sweep2d_grid.png")
