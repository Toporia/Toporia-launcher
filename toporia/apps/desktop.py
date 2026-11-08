# apps/desktop.py — the desktop program's one entry point: python main.py, and the Windows Toporia.exe.
#
#   Toporia.exe                      the desktop app
#   Toporia.exe --project FILE.top   open a project at start
#   Toporia.exe --worker INPUT.top   one run, as the app starts it in its own process
#   Toporia.exe --smoke-test         build the window, run a small optimisation, exit 0 if all is well
#
# A frozen (bundled) program has no separate python to start runs with, so the app starts
# itself with --worker; and worker processes for parallel sweeps need freeze_support().

import argparse
import multiprocessing
import sys


def frozen():
    """Whether this is the bundled Windows program rather than Python running the sources."""
    return bool(getattr(sys, "frozen", False))


def worker_command(input_path):
    """(program, arguments) that run one snapshot in its own process."""
    if frozen():
        return sys.executable, ["--worker", str(input_path)]
    from pathlib import Path
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    return str(executable), ["-u", "-m", "toporia.apps.gui_worker", str(input_path)]


def smoke_test():
    """Everything a bundle needs at once: plugins, the window, and an optimisation with output."""
    import contextlib
    import io
    import os
    import tempfile
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from toporia.apps.gui.window import MainWindow
    from toporia.engine.loop import run_single
    from toporia.plugins.problems import get_run, problem_names
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.processEvents()
    run = get_run("MBB Beam").updated(m=0.3, max_iter=5, save_every=0).with_output_dir(tempfile.mkdtemp())
    with contextlib.redirect_stdout(io.StringIO()):
        density = run_single(run)
    print(f"smoke test passed: {len(problem_names())} presets, design {density.shape}, "
          f"window '{window.windowTitle()}'")
    return 0


def _usable_streams():
    """A windowed (no console) program may start with sys.stdout None; use the handles it was given."""
    import os
    for name, fd in (("stdout", 1), ("stderr", 2)):
        if getattr(sys, name) is None:
            try:
                setattr(sys, name, open(fd, "w", encoding="utf-8", buffering=1, closefd=False))
            except OSError:
                setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def main(argv=None):
    multiprocessing.freeze_support()
    argv = sys.argv[1:] if argv is None else list(argv)
    _usable_streams()
    if argv[:1] == ["--worker"]:
        from toporia.apps.gui_worker import main as run_worker
        return run_worker(argv[1])
    parser = argparse.ArgumentParser(prog="Toporia", description="Toporia — topology optimisation desktop")
    parser.add_argument("--project", help="open a saved .top project")
    parser.add_argument("--smoke-test", action="store_true", help="check the installation and exit")
    args = parser.parse_args(argv)
    if args.smoke_test:
        return smoke_test()
    from toporia.apps.gui import launch
    return launch(args.project)


if __name__ == "__main__":
    raise SystemExit(main())
