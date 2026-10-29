"""Published numbers from open-access papers, reproduced with Toporia's own functions.

python -m experiments.research_papers [--case NAME] [--output DIR]

Each case runs a recipe built from a paper's stated settings and compares one
published number: a final compliance, or a compliance ratio to the paper's own
reference design. A case counts as a match when it is within MATCH (5 %); the
difference is recorded either way. The evidence goes to docs/research/evidence/papers.

Only papers with an open full text were used (arXiv), so settings could be read
rather than guessed. What the papers leave open (top99neo's move limit, the
machining paper's MMA settings and step count) is chosen here and stated.
"""

import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from toporia.engine.loop import run_single_with_store  # noqa: E402
from toporia.framework import Run  # noqa: E402
from toporia.plugins.problems import paper_machining_cantilever as machining  # noqa: E402
from toporia.plugins.problems import paper_top99neo_mbb as top99neo  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/research/evidence/papers"
MATCH = 0.05

TOP99NEO = "https://arxiv.org/abs/2005.05436"
MACHINING = "https://arxiv.org/abs/2102.12999"

#: name -> (recipe, published value, reference case for a ratio or None, source, target, functions shown)
CASES = {
    "top99neo_t1": (lambda: top99neo.recipe("T1"), 252.7, None, TOP99NEO,
                    "Ferrari & Sigmund (2020) Table 2, T1: density filter only, c = 252.7 after 2500 steps",
                    ("filter:density", "updater:oc")),
    "top99neo_t2": (lambda: top99neo.recipe("T2"), 246.1, None, TOP99NEO,
                    "Ferrari & Sigmund (2020) Table 2, T2: volume-preserving projection at beta 2, c = 246.1",
                    ("filter:heaviside",)),
    "top99neo_t3": (lambda: top99neo.recipe("T3"), 199.6, None, TOP99NEO,
                    "Ferrari & Sigmund (2020) Table 2, T3: as T2, beta +2 every 25 steps from step 250 to 16, c = 199.6",
                    ("filter:heaviside", "schedule:steps")),
    "machining_reference": (lambda: machining.recipe(()), 69.98, None, MACHINING,
                            "Hoghoj & Traff (2021) Table 2 / Fig. 5a: no milling constraint, c = 69.98",
                            ()),
    "machining_0": (lambda: machining.recipe(("pos_x",)), 2.57, "machining_reference", MACHINING,
                    "Hoghoj & Traff (2021) Fig. 5b: one tool at 0 degrees, 2.57 times the reference compliance",
                    ("filter:machining",)),
    "machining_180": (lambda: machining.recipe(("neg_x",)), 4.11, "machining_reference", MACHINING,
                      "Hoghoj & Traff (2021) Fig. 5f: one tool at 180 degrees, 4.11 times the reference compliance",
                      ("filter:machining",)),
    "machining_m90_0": (lambda: machining.recipe(("neg_y", "pos_x")), 3.15, "machining_reference", MACHINING,
                        "Hoghoj & Traff (2021) Fig. 6a: tools at -90 and 0 degrees, 3.15 times the reference",
                        ("filter:machining",)),
    "machining_m90_0_180": (lambda: machining.recipe(("neg_y", "pos_x", "neg_x")), 1.24, "machining_reference", MACHINING,
                            "Hoghoj & Traff (2021) Fig. 6b: tools at -90, 0 and 180 degrees, 1.24 times the reference",
                            ("filter:machining",)),
}


def run_case(name, output):
    recipe, published, reference, source, target, functions = CASES[name]
    scenario, solver = recipe()
    folder = Path(output) / name
    t0 = time.perf_counter()
    store, density = run_single_with_store(Run(scenario, solver).with_output_dir(folder / "run"))
    np.save(folder / "final-density.npy", density)
    record = dict(case_id=name, functions=list(functions), source_url=source, target=target,
                  published=published, compliance=float(store.objectives[-1]), iterations=len(store.objectives),
                  stop_reason=store.stop_reason, volume_fraction=float(density.mean()),
                  grayness=float(np.mean(4 * density * (1 - density))),
                  runtime_seconds=round(time.perf_counter() - t0, 1),
                  solver=dict(method=solver.method, m=solver.m, max_iter=solver.max_iter, tol=solver.tol,
                              filter_specs=solver.filter_specs, schedules=solver.schedules,
                              method_params=solver.method_params, interpolation=solver.interpolation))
    (folder / "record.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return record


def compare(records):
    """Add the measured value (compliance or ratio), its difference and the verdict to each record."""
    for name, record in records.items():
        reference = CASES[name][2]
        record["functions"] = list(CASES[name][5])
        if reference is None:
            measured = record["compliance"]
        elif reference in records:
            measured = record["compliance"] / records[reference]["compliance"]
        else:
            continue
        difference = measured / record["published"] - 1
        match = abs(difference) <= MATCH
        record.update(measured=measured, kind="ratio to " + reference if reference else "compliance",
                      relative_difference=difference,
                      paper_status="published_value_match" if match else "paper_reproduction_to_fix",
                      checks=dict(checks_passed=bool(np.isfinite(measured) and abs(record["volume_fraction"] - 0.5) < 1e-3),
                                  match_tolerance=MATCH))
    return records


def publish(records, folder):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for name, record in records.items():
        if "measured" not in record:
            continue
        target = EVIDENCE / name
        target.mkdir(exist_ok=True)
        density = np.load(Path(folder) / name / "final-density.npy")
        np.save(target / "final-density.npy", density)
        fig, ax = plt.subplots(figsize=(5, 5 * density.shape[0] / density.shape[1] + 0.6))
        ax.imshow(1 - density, cmap="gray", origin="lower", vmin=0, vmax=1)
        ax.set_axis_off()
        ax.set_title(f"{name}: {record['kind']} {record['measured']:.4g} (paper {record['published']:g}, "
                     f"{record['relative_difference']:+.1%})", fontsize=8)
        fig.tight_layout()
        fig.savefig(target / "figure.png", dpi=80)
        plt.close(fig)
        (target / "report.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", choices=["all", *CASES], default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "results/research/papers")
    parser.add_argument("--publish-only", action="store_true", help="compare and publish saved records")
    args = parser.parse_args()
    if not args.publish_only:
        for name in CASES if args.case == "all" else [args.case]:
            record = run_case(name, args.output)
            print(name, f"compliance {record['compliance']:.3f}", record["stop_reason"], flush=True)
    records = {}
    for name in CASES:
        path = args.output / name / "record.json"
        if path.exists():
            records[name] = json.loads(path.read_text(encoding="utf-8"))
    publish(compare(records), args.output)
    for name, record in records.items():
        if "measured" in record:
            print(f"{name}: {record['measured']:.4g} against {record['published']:g} "
                  f"({record['relative_difference']:+.1%}) {record['paper_status']}")


if __name__ == "__main__":
    main()
