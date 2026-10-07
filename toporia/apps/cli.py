"""toporia command line — the whole platform without the GUI.

    toporia                                          launch the GUI
    toporia list                                     presets, methods, filters, responses
    toporia export PRESET DIR                        write a preset as scenario + solver JSON
    toporia run SCENARIO [SOLVER]                    one optimisation
    toporia compare SCENARIO SOLVER_A SOLVER_B       same problem, two solvers
    toporia sweep SCENARIO [SOLVER] --param PATH --range MIN MAX [--grid ROWS COLS]
    toporia check [KIND:NAME ...] [--quick]          conformance test of plugins (all by default)
    toporia benchmark --methods M ... [--problems P ...] [--set PATH=VALUE] [--out DIR]
                                                     several methods on several problems, one table
    toporia post FOLDER TYPE[:PARAM=VALUE,...] ...   post-process a saved run again, e.g.
                                                     toporia post results/mbb threshold export_stl:thickness=3

SCENARIO is a scenario JSON file or a preset name such as "MBB Beam".
SOLVER is a solver JSON file; without one, a preset's recommended solver (or the
defaults) is used.

Every command that runs accepts --out DIR and any number of --set PATH=VALUE,
where PATH is a parameter path:

    toporia run "MBB Beam" --set method=q4+mma --set interpolation.penal=4 --set volfrac=0.3

VALUE is parsed as JSON when it can be (numbers, lists, objects) and taken as a
plain string otherwise.  Post-processors run after any run with, for example,

    toporia run "MBB Beam" --set 'postprocess=[{"type": "threshold"}, {"type": "export_dxf"}]'
"""

import argparse
import json
import re
from dataclasses import replace
from pathlib import Path


def main(argv=None) -> int:
    """Parse the command line and run the command; no command opens the GUI.  Returns the exit code."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command in (None, "gui"):
        from toporia.apps.gui import launch
        launch()
        return 0
    return args.handler(args)


# ── Building a Run from the command line ──────────────────────────────────────

def _parse_override(text):
    path, sep, raw = text.partition("=")
    if not sep or not path:
        raise SystemExit(f"--set expects PATH=VALUE, got {text!r}")
    try:
        return path.strip(), json.loads(raw)
    except ValueError:
        return path.strip(), raw


def _build_run(scenario_arg, solver_arg=None, overrides=(), out=None):
    from toporia.framework import Run, apply_param
    from toporia.framework.problem.files import load
    from toporia.plugins.problems import get_run, problem_names

    if Path(scenario_arg).is_file():
        run = Run(scenario=load(scenario_arg, "scenario"))
    elif scenario_arg in problem_names():
        run = get_run(scenario_arg)
    else:
        raise SystemExit(f"{scenario_arg!r} is neither a scenario file nor a preset. "
                         f"Presets: {problem_names()}")
    if solver_arg:
        run = replace(run, solver=load(solver_arg, "solver"))
    for item in overrides:
        run = apply_param(run, *_parse_override(item))
    if out:
        run = run.with_output_dir(out)
    return run


def _label(solver_path):
    return Path(solver_path).name.removesuffix(".json").removesuffix(".solver")


# ── Commands ──────────────────────────────────────────────────────────────────

def _cmd_list(args):
    from toporia.plugins.filters import FILTERS
    from toporia.plugins.interpolations import INTERPOLATIONS
    from toporia.plugins.methods import METHODS, PRESETS
    from toporia.plugins.models import MODELS
    from toporia.plugins.postprocessors import POSTPROCESSORS
    from toporia.plugins.problems import problem_names
    from toporia.plugins.representations import REPRESENTATIONS
    from toporia.plugins.responses import RESPONSES
    from toporia.plugins.schedules import SCHEDULES
    from toporia.plugins.updaters import UPDATERS

    print("Presets:")
    for name in problem_names():
        print(f"  {name}")
    print("\nA method is '<model>+<updater>' (any pair), or a whole method.")
    from toporia.framework.registry import BUILT_IN, missing_dependencies

    for title, registry in (("Models", MODELS), ("Updaters", UPDATERS), ("Whole methods", METHODS),
                            ("Design representations", REPRESENTATIONS), ("Filters", FILTERS),
                            ("Material laws", INTERPOLATIONS), ("Responses", RESPONSES),
                            ("Schedules", SCHEDULES), ("Post-processors", POSTPROCESSORS)):
        print(f"\n{title}:")
        for cls in registry.classes():
            params = ", ".join(p.name for p in cls.params) or "-"
            notes = []
            if registry.source(cls.name) != BUILT_IN:
                notes.append(f"from {registry.source(cls.name)}")
            missing = missing_dependencies(cls)
            if missing:
                notes.append(f"NOT INSTALLED: needs {', '.join(missing)}")
            extra = f"  [{'; '.join(notes)}]" if notes else ""
            print(f"  {cls.name:<18} {cls.label:<32} params: {params}{extra}")
        for where, message in registry.errors:
            print(f"  NOT LOADED  {where}: {message}")
    print("\nOlder method names:")
    for old, new in PRESETS.items():
        print(f"  {old:<18} = {new}")
    return 0


def _cmd_post(args):
    from toporia.engine.postprocess import postprocess_folder

    specs = []
    for text in args.postprocessors:
        name, _, rest = text.partition(":")
        spec = {"type": name}
        for item in filter(None, rest.split(",")):
            key, value = _parse_override(item)
            spec[key] = value
        specs.append(spec)
    done = postprocess_folder(Path(args.folder), specs)
    return 1 if any("error" in entry for entry in done.values()) else 0


def _cmd_export(args):
    from toporia.framework.problem.files import save
    from toporia.plugins.problems import get_run, problem_names

    if args.preset not in problem_names():
        raise SystemExit(f"Unknown preset {args.preset!r}. Presets: {problem_names()}")
    run = get_run(args.preset)
    slug = re.sub(r"\W+", "_", args.preset.lower()).strip("_")
    for obj, kind in ((run.scenario, "scenario"), (run.solver, "solver")):
        print(f"wrote {save(obj, Path(args.dir) / f'{slug}.{kind}.json')}")
    return 0


def _cmd_run(args):
    from toporia.engine.loop import run_single_with_store

    run = _build_run(args.scenario, args.solver, args.set, args.out)
    store, _ = run_single_with_store(run)
    print(f"\nobjective {store.objectives[-1]:.6g} after {len(store.objectives)} iterations "
          f"({store.stop_reason})")
    print(f"results in {run.output.dir}")
    return 0


def _cmd_compare(args):
    from toporia.engine.modes.compare import compare_runs

    label_a, label_b = _label(args.solver_a), _label(args.solver_b)
    base = _build_run(args.scenario, None, (), args.out)
    out_dir = Path(base.output.dir) / f"compare_{label_a}_vs_{label_b}"
    run_a = _build_run(args.scenario, args.solver_a, args.set).with_output_dir(out_dir / "run_A")
    run_b = _build_run(args.scenario, args.solver_b, args.set).with_output_dir(out_dir / "run_B")
    image, _, _ = compare_runs(run_a, run_b, label_a, label_b, out_dir)
    print(f"comparison in {image}")
    return 0


def _cmd_sweep(args):
    from toporia.engine.modes.sweep import sweep

    run = _build_run(args.scenario, args.solver, args.set, args.out)
    rows, cols = args.grid
    sweep(args.param, args.range[0], args.range[1], rows, cols, run)
    print(f"grid in {Path(run.output.dir) / f'sweep_{args.param}' / 'sweep_grid.png'}")
    return 0


def _cmd_benchmark(args):
    from toporia.engine.modes.methods import benchmark
    from toporia.plugins.problems import problem_names

    problems = args.problems or ["MBB Beam"]
    unknown = [name for name in problems if name not in problem_names()]
    if unknown:
        raise SystemExit(f"Unknown problem(s) {unknown}. Presets: {problem_names()}")
    overrides = dict(_parse_override(text) for text in args.set)
    out = Path(args.out) if args.out else Path("results") / "benchmark"
    rows = benchmark(args.methods, problems, overrides, out)
    print(f"\ntable in {out / 'benchmark.csv'}")
    return 0 if all(row["status"] == "ran" for row in rows) else 1


def _cmd_check(args):
    from toporia.checks import all_plugins, conformance

    targets = args.plugins or all_plugins()
    failed = []
    for target in targets:
        quick = {"benchmark": False} if args.quick and target.startswith("updater:") else {}
        report = conformance(target, **quick)
        print(report, end="\n\n")
        if not report.ok:
            failed.append(target)
    print(f"{len(targets) - len(failed)} of {len(targets)} conform" +
          (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


# ── Argument parsing ──────────────────────────────────────────────────────────

def _parser():
    parser = argparse.ArgumentParser(
        prog="toporia", description="Topology optimisation platform. Run without a command for the GUI.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__,
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("gui", help="launch the GUI (the default)")
    commands.add_parser("list", help="show presets, methods and filters").set_defaults(handler=_cmd_list)

    check = commands.add_parser("check", help="conformance test of plugins, as kind:name (all by default)")
    check.add_argument("plugins", nargs="*", metavar="KIND:NAME", help="e.g. updater:mma filter:density")
    check.add_argument("--quick", action="store_true", help="skip the updater benchmark")
    check.set_defaults(handler=_cmd_check)

    bench = commands.add_parser("benchmark", help="several methods on several problems, one table")
    bench.add_argument("--methods", nargs="+", required=True, metavar="METHOD",
                       help='e.g. q4+oc q4+mma levelset ("<model>+<updater>" or a whole method)')
    bench.add_argument("--problems", nargs="+", metavar="PRESET", help='default: "MBB Beam"')
    bench.add_argument("--set", action="append", default=[], metavar="PATH=VALUE",
                       help="applied to every problem, e.g. m=0.5 max_iter=80 (repeatable)")
    bench.add_argument("--out", help="output directory (default results/benchmark)")
    bench.set_defaults(handler=_cmd_benchmark)

    post = commands.add_parser("post", help="post-process a saved run again (threshold, checks, exports)")
    post.add_argument("folder", help="a run's output folder (with run.json and final_density.csv)")
    post.add_argument("postprocessors", nargs="+", metavar="TYPE[:PARAM=VALUE,...]",
                      help="e.g. threshold connectivity export_stl:thickness=3")
    post.set_defaults(handler=_cmd_post)

    export = commands.add_parser("export", help="write a preset as scenario + solver JSON files")
    export.add_argument("preset")
    export.add_argument("dir")
    export.set_defaults(handler=_cmd_export)

    def running(name, help_text, handler):
        """A sub-command that runs optimisations: a scenario, --out and any number of --set."""
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("scenario", help="scenario JSON file or preset name")
        sub.add_argument("--out", help="output directory")
        sub.add_argument("--set", action="append", default=[], metavar="PATH=VALUE",
                         help="override one parameter path (repeatable)")
        sub.set_defaults(handler=handler)
        return sub

    run = running("run", "run one optimisation", _cmd_run)
    run.add_argument("solver", nargs="?", help="solver JSON file")

    compare = running("compare", "solve one scenario with two solvers and compare", _cmd_compare)
    compare.add_argument("solver_a")
    compare.add_argument("solver_b")

    sweep = running("sweep", "vary one parameter over a grid of runs", _cmd_sweep)
    sweep.add_argument("solver", nargs="?", help="solver JSON file")
    sweep.add_argument("--param", required=True, help="parameter path to vary, e.g. volfrac")
    sweep.add_argument("--range", required=True, nargs=2, type=float, metavar=("MIN", "MAX"))
    sweep.add_argument("--grid", nargs=2, type=int, default=(3, 3), metavar=("ROWS", "COLS"))
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
