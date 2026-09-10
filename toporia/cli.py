"""toporia command line — the whole platform without the GUI.

    toporia                                          launch the GUI
    toporia list                                     presets, methods and filters
    toporia export PRESET DIR                        write a preset as scenario + solver JSON
    toporia run SCENARIO [SOLVER]                    one optimisation
    toporia compare SCENARIO SOLVER_A SOLVER_B       same problem, two solvers
    toporia sweep SCENARIO [SOLVER] --param PATH --range MIN MAX [--grid ROWS COLS]

SCENARIO is a scenario JSON file or a preset name such as "MBB Beam".
SOLVER is a solver JSON file; without one, a preset's recommended solver (or the
defaults) is used.

Every command that runs accepts --out DIR and any number of --set PATH=VALUE,
where PATH is a parameter path:

    toporia run "MBB Beam" --set method=density_mma --set method.penal=4 --set volfrac=0.3

VALUE is parsed as JSON when it can be (numbers, lists, objects) and taken as a
plain string otherwise.
"""

import argparse
import json
import re
from dataclasses import replace
from pathlib import Path


def main(argv=None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command in (None, "gui"):
        from toporia.gui import launch
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
    from toporia.core import Run, apply_param
    from toporia.core.serialize import load
    from toporia.library.problems import get_run, problem_names

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
    from toporia.library.methods import METHODS
    from toporia.library.methods.filters import FILTERS
    from toporia.library.problems import problem_names

    print("Presets:")
    for name in problem_names():
        print(f"  {name}")
    for title, registry in (("Methods", METHODS), ("Filters", FILTERS)):
        print(f"\n{title}:")
        for cls in registry.classes():
            params = ", ".join(p.name for p in cls.params) or "-"
            print(f"  {cls.name:<12} {cls.label:<32} params: {params}")
    return 0


def _cmd_export(args):
    from toporia.core.serialize import save
    from toporia.library.problems import get_run, problem_names

    if args.preset not in problem_names():
        raise SystemExit(f"Unknown preset {args.preset!r}. Presets: {problem_names()}")
    run = get_run(args.preset)
    slug = re.sub(r"\W+", "_", args.preset.lower()).strip("_")
    for obj, kind in ((run.scenario, "scenario"), (run.solver, "solver")):
        print(f"wrote {save(obj, Path(args.dir) / f'{slug}.{kind}.json')}")
    return 0


def _cmd_run(args):
    from toporia.engine.runner import run_single_with_store

    run = _build_run(args.scenario, args.solver, args.set, args.out)
    store, _ = run_single_with_store(run)
    print(f"\nobjective {store.objectives[-1]:.6g} after {len(store.objectives)} iterations "
          f"({store.stop_reason})")
    print(f"results in {run.output.dir}")
    return 0


def _cmd_compare(args):
    from toporia.engine.compare_core import compare_core

    label_a, label_b = _label(args.solver_a), _label(args.solver_b)
    base = _build_run(args.scenario, None, (), args.out)
    out_dir = Path(base.output.dir) / f"compare_{label_a}_vs_{label_b}"
    run_a = _build_run(args.scenario, args.solver_a, args.set).with_output_dir(out_dir / "run_A")
    run_b = _build_run(args.scenario, args.solver_b, args.set).with_output_dir(out_dir / "run_B")
    image, _, _ = compare_core(run_a, run_b, label_a, label_b, out_dir)
    print(f"comparison in {image}")
    return 0


def _cmd_sweep(args):
    from toporia.engine.sweep import sweep

    run = _build_run(args.scenario, args.solver, args.set, args.out)
    rows, cols = args.grid
    sweep(args.param, args.range[0], args.range[1], rows, cols, run)
    print(f"grid in {Path(run.output.dir) / f'sweep_{args.param}' / 'sweep_grid.png'}")
    return 0


# ── Argument parsing ──────────────────────────────────────────────────────────

def _parser():
    parser = argparse.ArgumentParser(
        prog="toporia", description="Topology optimisation platform. Run without a command for the GUI.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__,
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("gui", help="launch the GUI (the default)")
    commands.add_parser("list", help="show presets, methods and filters").set_defaults(handler=_cmd_list)

    export = commands.add_parser("export", help="write a preset as scenario + solver JSON files")
    export.add_argument("preset")
    export.add_argument("dir")
    export.set_defaults(handler=_cmd_export)

    def running(name, help_text, handler):
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
