"""Attempt the PTOc Figure 3 MBB example with Toporia's distinct PTO variant, and reproduce it with PTOc.

The sensitivity-proxy `pto` variant is compared and its mismatch kept; the original
`ptoc` updater must match the captured author run (native_code_match).

python -m experiments.research_pto_attempt
Optional fresh native capture:
python -m experiments.research_pto_attempt --capture --source-dir PATH --matlab-exe PATH

The author code is not redistributed. Supply the unchanged PLOS S2 supplement
as PTOc_mbb.m; its SHA-256 is checked before MATLAB starts. Numerical outputs
and the failed comparison are preserved; the implementation is not changed.
"""

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from experiments.research_batch3 import dump
from toporia.engine.loop import _loop, initialized_method
from toporia.engine.records import ResultStore
from toporia.framework import LoadCase, PointConstraint, PointLoad
from toporia.framework.problem.run import Run
from toporia.plugins.problems._research_batch3 import recipe

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/references/paper_ptoc.json"
SOURCE_HASH = "658169ac413d17cf62471c84bf63cab0611d39f6be00c12f645b46525980a88d"
SOURCE_URL = "https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0145041.s002"


def capture(source_dir, matlab):
    source = Path(source_dir) / "PTOc_mbb.m"
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_HASH:
        raise ValueError("PTOc_mbb.m hash differs from the reviewed PLOS author source")
    with tempfile.TemporaryDirectory(prefix="ptoc-capture-", dir=Path(source_dir).resolve().parent) as temporary:
        folder = Path(temporary)
        shutil.copyfile(source, folder / source.name)
        script = """set(groot,'defaultFigureVisible','off');
report.runtime=version;
report.command='PTOc_mbb(0.5,1,1e-9,1,1,3,120,40,0.3,3,1.5,0.35,[0 1])';
printed=evalc('x=PTOc_mbb(0.5,1,1e-9,1,1,3,120,40,0.3,3,1.5,0.35,[0 1]);');
tokens=regexp(printed,'It:\\s*(\\d+)\\s+Max_vms:\\s*([\\d.eE+-]+)\\s+Comp:\\s*([\\d.eE+-]+)\\s+Vol:\\s*([\\d.eE+-]+)\\s+Ch:\\s*([\\d.eE+-]+|Inf)','tokens');
assert(~isempty(tokens),'No source trace');
report.history=zeros(numel(tokens),5);
for j=1:numel(tokens), report.history(j,:)=cellfun(@str2double,tokens{j}); end
report.density=x; report.iterations=numel(tokens);
fid=fopen('capture.json','w'); fprintf(fid,'%s',jsonencode(report)); fclose(fid);
close all force;
"""
        (folder / "capture.m").write_text(script, encoding="utf-8")
        prefs = folder / "prefs"
        prefs.mkdir()
        completed = subprocess.run([str(matlab), "-batch", "run('capture.m');"], cwd=folder,
                                   env={**os.environ, "MATLAB_PREFDIR": str(prefs)}, capture_output=True,
                                   text=True, timeout=900, check=False)
        if completed.returncode:
            raise RuntimeError(completed.stdout + "\n" + completed.stderr)
        result = json.loads((folder / "capture.json").read_text(encoding="utf-8"))
    result.update(source_url=SOURCE_URL, source_sha256=SOURCE_HASH,
                  captured_at=datetime.now(timezone.utc).isoformat(),
                  target="Biyikli-To (2015) Figure 3, half-MBB PTOc density and compliance panels",
                  density_order="Author row zero at top; flip vertically once for Toporia bottom-origin fields.",
                  protocol="Unchanged author source. alpha=.5, 120x40, fraction .35, p=3, r=1.5, load split across three top-left nodes, vertical supports at (120,0),(120,1),(120,2) on the right edge. History: step, printed max stress, printed compliance, printed fraction, prior change. Last printed field is the returned field; the author tests termination before updating.")
    return result


def attempt(reference, output):
    if reference["source_sha256"] != SOURCE_HASH:
        raise ValueError("Reference provenance differs")
    output.mkdir(parents=True, exist_ok=True)
    scenario, solver = recipe("pto")
    scenario = replace(scenario, Lx=120., Ly=40., volfrac=.35,
                       point_loads=[PointLoad(x=float(x), y=40.) for x in range(3)],
                       load_cases=[LoadCase(Fmag=1/3, Fa=270.)],
                       point_constraints=[PointConstraint(x=120., y=float(y), dof="y") for y in range(3)])
    # Align the source's linear allocation and history blend where possible;
    # the existing sensitivity proxy, move handling and filter placement differ.
    solver = replace(solver, m=1., max_iter=600, tol=.01, method_params=dict(q=1., relax=.5, move=1.))
    run = Run(scenario, solver).with_output_dir(output / "run")
    with (output / "execution.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
        method = initialized_method(run)
        store = ResultStore(run.output.dir)
        expected = np.flipud(np.array(reference["density"]))
        state = method._model.engine.solve(expected)
        native_fresh = float(np.dot(state.weights, state.compliances))
        if abs(native_fresh-reference["history"][-1][2]) >= .0051:
            method.close()
            raise ValueError("Author field does not match printed compliance on this physics setup; resolve support/load/material mapping first")
        try:
            iterations, stop = _loop(run, method, store, None)
        finally:
            method.close()
        actual = method.get_density().copy()
        current = method._model.evaluate(method.x, gradients=False)
    field_error = float(np.max(abs(actual-expected)))
    relative_c = float(abs(current.objective-native_fresh)/native_fresh)
    report = dict(source_sha256=SOURCE_HASH, target=reference["target"], source_url=SOURCE_URL,
                  author_iterations=reference["iterations"], toporia_iterations=iterations,
                  author_field_fresh_compliance=native_fresh, toporia_fresh_compliance=float(current.objective),
                  author_last_printed_compliance=reference["history"][-1][2],
                  physics_print_tolerance=.0051,
                  author_field_physics_match=abs(native_fresh-reference["history"][-1][2]) < .0051,
                  density_max_error=field_error, relative_compliance_error=relative_c,
                  tolerances=dict(density_max_abs=1e-6, relative_compliance=1e-6),
                  native_code_match=bool(field_error < 1e-6 and relative_c < 1e-6),
                  physical_fraction=float(actual.mean()), author_fraction=float(expected.mean()),
                  stop_reason=stop, paper_status="paper_reproduction_to_fix",
                  settings="120x40 unit cells, .35 volume, r=1.5, p=3, q=1, relax=.5, move=1, 600-step cap, change tol=.01; downward forces 1/3 at (0,40),(1,40),(2,40); vertical rollers (120,0),(120,1),(120,2); left horizontal symmetry.",
                  reason="Toporia allocates from negative filtered sensitivity and filters trial design for volume; PTOc allocates from physical element compliance with a filtered redistribution inner loop and history blend. Similar topology/compliance cannot erase the formulation difference.")
    dump(output / "report.json", report)
    np.savetxt(output / "toporia-density.csv", actual, delimiter=",")
    np.savetxt(output / "author-density-bottom-origin.csv", expected, delimiter=",")
    np.savetxt(output / "toporia-history.csv", np.column_stack([np.arange(1, iterations+1), store.objectives, store.volumes]), delimiter=",")
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    fig = Figure(figsize=(11, 7), dpi=150, facecolor="white")
    FigureCanvasAgg(fig)
    axes = fig.subplots(2, 2)
    for ax, field, label in ((axes[0, 0], expected, "Unchanged author PTOc"), (axes[0, 1], actual, "Toporia sensitivity-proxy variant")):
        ax.imshow(field, origin="lower", cmap="gray_r", vmin=0, vmax=1, extent=(0, 120, 0, 40))
        ax.set(title=label, xlabel="x (unit cells)", ylabel="y")
    axes[1, 0].semilogy(np.arange(1, iterations+1), store.objectives, label="Toporia recorded C")
    trace = np.array(reference["history"], dtype=float)
    axes[1, 0].semilogy(trace[:, 0], trace[:, 2], label="Author printed C")
    axes[1, 0].set(xlabel="Iteration", ylabel="Compliance")
    axes[1, 0].legend()
    im = axes[1, 1].imshow(abs(actual-expected), origin="lower", cmap="magma", extent=(0, 120, 0, 40), vmin=0, vmax=1)
    axes[1, 1].set(title=f"Density difference; max {field_error:.3f}", xlabel="x (unit cells)", ylabel="y")
    fig.colorbar(im, ax=axes[1, 1], orientation="horizontal", fraction=.1, pad=.3)
    fig.suptitle("PTOc Figure 3 MBB attempt — formulation mismatch retained", x=.05, ha="left")
    fig.tight_layout(rect=(0, 0, 1, .94))
    fig.savefig(output / "figure.png")
    return report


def reproduce_ptoc(reference, output):
    """Run the original PTOc preset and compare it with the captured author run, step by step."""
    from toporia.plugins.problems import get_run
    output.mkdir(parents=True, exist_ok=True)
    run = get_run("Paper: PTOc Fig. 3 (MBB)").with_output_dir(output / "run")
    with (output / "execution.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
        method = initialized_method(run)
        store = ResultStore(run.output.dir)
        try:
            iterations, stop = _loop(run, method, store, None)
        finally:
            method.close()
        actual = method.get_density().copy()
    expected = np.flipud(np.array(reference["density"]))
    printed = np.array([row[2] for row in reference["history"]], dtype=float)
    ours = np.array(store.objectives)
    n = min(len(ours), len(printed))
    print_errors = np.abs(np.round(ours[:n], 2) - printed[:n])
    field_error = float(np.max(abs(actual - expected)))
    match = bool(iterations == reference["iterations"] - 1 and np.all(print_errors <= .0051) and field_error < 1e-6)
    report = dict(schema=1, case_id="ptoc", functions=["updater:ptoc"], source_sha256=SOURCE_HASH,
                  source_url=SOURCE_URL, target=reference["target"],
                  paper_status="native_code_match" if match else "paper_reproduction_to_fix",
                  paper_visual_status="not_assessed", stop_reason=stop, iterations=iterations,
                  author_printed_lines=reference["iterations"],
                  checks=dict(checks_passed=match, printed_compliance_mismatches=int(np.sum(print_errors > .0051)),
                              compared_iterations=n, density_max_error=field_error,
                              tolerances=dict(printed_compliance=.0051, density_max_abs=1e-6)),
                  final_compliance=float(ours[-1]), physical_fraction=float(actual.mean()),
                  scope="Unchanged author PTOc_mbb.m captured in MATLAB R2026a against Toporia's ptoc updater on the "
                        "same 120x40 setup. The author prints one more line because termination is tested before "
                        "the update; the returned fields are compared.")
    dump(output / "report.json", report)
    np.savetxt(output / "toporia-density.csv", actual, delimiter=",")
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    fig = Figure(figsize=(11, 7), dpi=150, facecolor="white")
    FigureCanvasAgg(fig)
    axes = fig.subplots(2, 2)
    for ax, field, label in ((axes[0, 0], expected, "Unchanged author PTOc"), (axes[0, 1], actual, "Toporia ptoc")):
        ax.imshow(field, origin="lower", cmap="gray_r", vmin=0, vmax=1, extent=(0, 120, 0, 40))
        ax.set(title=label, xlabel="x (unit cells)", ylabel="y")
    axes[1, 0].semilogy(np.arange(1, len(ours)+1), ours, label="Toporia ptoc")
    axes[1, 0].semilogy(np.arange(1, len(printed)+1), printed, "--", label="Author printed")
    axes[1, 0].set(xlabel="Iteration", ylabel="Compliance")
    axes[1, 0].legend()
    im = axes[1, 1].imshow(abs(actual-expected), origin="lower", cmap="magma", extent=(0, 120, 0, 40))
    axes[1, 1].set(title=f"Density difference; max {field_error:.1e}", xlabel="x (unit cells)", ylabel="y")
    fig.colorbar(im, ax=axes[1, 1], orientation="horizontal", fraction=.1, pad=.3)
    fig.suptitle("PTOc Figure 3 MBB — native-code reproduction", x=.05, ha="left")
    fig.tight_layout(rect=(0, 0, 1, .94))
    fig.savefig(output / "figure.png")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--matlab-exe", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "results/research/batch3/pto-paper-attempt")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.capture:
        if args.source_dir is None or args.matlab_exe is None:
            parser.error("--capture needs --source-dir and --matlab-exe")
        reference = capture(args.source_dir, args.matlab_exe)
        dump(args.output / "author-capture.json", reference)
    else:
        reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    report = attempt(reference, args.output)
    print(json.dumps(report, indent=2))
    reproduction = reproduce_ptoc(reference, args.output / "ptoc")
    print(json.dumps(reproduction, indent=2))
    # The variant's mismatch is expected and recorded; only the original PTOc must match.
    if reproduction["paper_status"] != "native_code_match":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
