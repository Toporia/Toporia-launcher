"""Reproduce named paper panels and compare against captured unchanged author code.

python -m experiments.research_figures [--case density|sensitivity|all]
python -m experiments.research_figures --capture-original --source-dir PATH --matlab-exe PATH

Original captures go to the requested output folder, never overwrite a fixture.
No solver implementation or golden baseline is changed. No source is downloaded.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from toporia.apps.research_render import description_page
from toporia.engine.loop import initialized_method
from toporia.plugins.problems import get_run, problem_description

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/references/paper_top88.json"
SOURCE_HASH = "2ae6c7a9308f9da0a602d372c799cd6e43ad61c2ac034f6b54d34ead1c5477a2"
SOURCE_URL = "https://www.topopt.mek.dtu.dk/-/media/subsites/topopt/apps/dokumenter-og-filer-til-apps/top88.m"
PRESETS = {kind: "Paper: top88 Fig. 3(a) - " + kind.capitalize() for kind in ("density", "sensitivity")}


def capture_original(source_dir, executable):
    """Run hash-identified author source unchanged, isolated from MATLAB settings."""
    supplied = Path(source_dir) / "top88.m"
    if hashlib.sha256(supplied.read_bytes()).hexdigest() != SOURCE_HASH:
        raise ValueError("top88.m hash differs from the reviewed author source")
    with tempfile.TemporaryDirectory(prefix="toporia-paper-top88-", dir=Path(source_dir).resolve().parent) as temporary:
        scratch = Path(temporary)
        shutil.copyfile(supplied, scratch / "top88.m")
        script = r"""set(groot,'defaultFigureVisible','off');
report.runtime=version;
names={'sensitivity','density'};
for ft=1:2
  output=evalc('top88(60,20,0.5,3,2.4,ft)');
  tokens=regexp(output,'It.:\s*(\d+)\s+Obj.:\s*([\d.eE+-]+)\s+Vol.:\s*([\d.eE+-]+)\s+ch.:\s*([\d.eE+-]+)','tokens');
  assert(~isempty(tokens),'No author iteration output');
  image=findobj(gcf,'Type','image'); assert(numel(image)==1,'Unexpected author figure');
  item.command=sprintf('top88(60,20,0.5,3,2.4,%d)',ft);
  item.density=1-get(image,'CData');
  item.iterations=numel(tokens);
  item.history=zeros(numel(tokens),4);
  for j=1:numel(tokens), item.history(j,:)=cellfun(@str2double,tokens{j}); end
  report.cases.(names{ft})=item;
  close all force;
end
fid=fopen('capture.json','w'); fprintf(fid,'%s',jsonencode(report)); fclose(fid);
"""
        (scratch / "capture.m").write_text(script, encoding="utf-8")
        preferences = scratch / "matlab-prefs"
        preferences.mkdir()
        environment = {**os.environ, "MATLAB_PREFDIR": str(preferences)}
        completed = subprocess.run([str(executable), "-batch", "run('capture.m');"], cwd=scratch,
                                   capture_output=True, text=True, timeout=900, check=False, env=environment)
        if completed.returncode:
            raise RuntimeError(f"Original run failed:\n{completed.stdout}\n{completed.stderr}")
        report = json.loads((scratch / "capture.json").read_text(encoding="utf-8"))
    report.update(source_url=SOURCE_URL, source_sha256=SOURCE_HASH,
                  captured_at=datetime.now(timezone.utc).isoformat(),
                  paper="https://doi.org/10.1007/s00158-010-0594-7", figure="3(a), top and bottom",
                  density_order="Author image rows top to bottom; columns left to right. Compare after one vertical flip.",
                  protocol="Unchanged author top88; 60x20, v=0.5, p=3, rmin=2.4. "
                           "History columns: iteration, pre-update printed compliance, printed volume, change. "
                           "Density is the final plotted physical field, extracted from image CData. "
                           "Printed compliance is not the fresh final-design compliance.")
    return report


def solve(kind):
    """Execute the actual selectable preset, retaining pre-update and fresh metrics."""
    run = get_run(PRESETS[kind])
    method = initialized_method(run)
    history = []
    try:
        for iteration in range(1, run.solver.max_iter + 1):
            method.step(iteration)
            history.append([iteration, float(method.get_responses()["objective"]),
                            float(method.get_density().mean()), float(method.get_change())])
            if method.get_change() < run.solver.tol:
                break
        density = method.get_density().copy()
        # Do this only after collecting the trace: evaluation updates filter caches.
        fresh = method._model.evaluate(method.x, gradients=False)
        return {"preset": PRESETS[kind], "density": density.tolist(), "history": history,
                "iterations": iteration, "stop_reason": "tolerance" if history[-1][3] < run.solver.tol else "max_iter",
                "fresh_final_compliance": float(fresh.objective), "physical_volume_fraction": float(density.mean()),
                "density_order": "row 0 at physical y=0 (bottom); columns left to right"}
    finally:
        method.close()


def compare(result, reference):
    """Accept numerical reproduction independently of the visual paper comparison."""
    actual = np.asarray(result["density"])
    # Author MATLAB numbers/image rows from the top; Toporia uses physical y=0
    # at row zero. This declared coordinate conversion is not an optimized fit.
    expected = np.flipud(np.asarray(reference["density"]))
    trace = np.asarray(result["history"])
    native_trace = np.asarray(reference["history"])
    same_iterations = result["iterations"] == reference["iterations"]
    field_error = float(np.max(np.abs(actual - expected))) if actual.shape == expected.shape else None
    compliance_error = float(np.max(np.abs(trace[:, 1] - native_trace[:, 1]))) if same_iterations else None
    checks = {
        "same_iterations": same_iterations,
        "field_shape": actual.shape == expected.shape,
        "final_density_max_abs_error": field_error,
        "pre_update_compliance_max_abs_error": compliance_error,
        "volume_error": float(abs(actual.mean() - expected.mean())),
        "coordinate_conversion": "flip author rows once: top-down image to bottom-up physical y",
        "tolerances": {"density_abs": 1e-7, "printed_compliance_abs": 5.1e-5, "volume_abs": 1e-8},
    }
    checks["native_code_match"] = bool(same_iterations and field_error is not None and field_error <= 1e-7
                                       and compliance_error is not None and compliance_error <= 5.1e-5
                                       and checks["volume_error"] <= 1e-8)
    # Paper identity cannot be inferred from a native-code numerical comparison.
    checks["paper_panel_status"] = "visual_review_required"
    return checks


def plot_comparison(kind, result, reference, comparison, destination):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    actual, expected = np.asarray(result["density"]), np.flipud(np.asarray(reference["density"]))
    figure = Figure(figsize=(12, 6.2), dpi=150, facecolor="white")
    FigureCanvasAgg(figure)
    grid = figure.add_gridspec(2, 3, height_ratios=[1, 1.05], hspace=.65, wspace=.28)
    for col, field, title in ((0, expected, "Unchanged author top88"), (1, actual, "Toporia research preset")):
        axis = figure.add_subplot(grid[0, col])
        axis.imshow(field, cmap="gray_r", vmin=0, vmax=1, origin="lower", interpolation="nearest")
        axis.set_title(title, fontsize=11)
        axis.set_axis_off()
    axis = figure.add_subplot(grid[0, 2])
    error = np.abs(actual - expected)
    shown = axis.imshow(error, cmap="magma", vmin=0, vmax=max(1e-10, float(error.max())), origin="lower", interpolation="nearest")
    axis.set_title(f"Absolute density error: max {error.max():.2e}", fontsize=10)
    axis.set_axis_off()
    figure.colorbar(shown, ax=axis, fraction=.035, pad=.03)
    axis = figure.add_subplot(grid[1, :2])
    trace, native = np.asarray(result["history"]), np.asarray(reference["history"])
    axis.plot(native[:, 0], native[:, 1], color="#b26b21", linewidth=3, alpha=.65, label="Author (printed)")
    axis.plot(trace[:, 0], trace[:, 1], color="#1c5779", linestyle="--", linewidth=1.6, label="Toporia")
    axis.set_xlabel("Iteration")
    axis.set_ylabel("Pre-update compliance")
    axis.grid(alpha=.18)
    axis.legend(frameon=False)
    axis = figure.add_subplot(grid[1, 2])
    axis.axis("off")
    status = "PASS" if comparison["native_code_match"] else "TO FIX"
    axis.text(0, .98, f"Native comparison: {status}\n\nIterations: {result['iterations']}\n"
              f"Physical volume: {actual.mean():.8f}\n"
              f"Last printed C: {trace[-1, 1]:.6f}\n"
              f"Fresh final C: {result['fresh_final_compliance']:.6f}\n\n"
              "Paper panel: separate visual review\n60 x 20; radius 2.4; p=3; OC",
              va="top", fontsize=10, linespacing=1.6)
    figure.suptitle(f"Andreassen et al. Figure 3(a): {kind} filtering", fontsize=15, x=.06, ha="left")
    figure.text(.06, .015, "Final physical fields, no thresholding. Reference: unchanged, hash-identified author code; DOI 10.1007/s00158-010-0594-7.", fontsize=8)
    figure.subplots_adjust(left=.06, right=.96, top=.88, bottom=.12)
    figure.savefig(destination, dpi=150)


def run_case(kind, reference, output):
    result = solve(kind)
    comparison = compare(result, reference["cases"][kind])
    folder = output / ("verified-native" if comparison["native_code_match"] else "to-fix") / kind
    folder.mkdir(parents=True, exist_ok=True)
    report = {"case": kind, "comparison": comparison, "result": result,
              "source_sha256": reference["source_sha256"], "python": platform.python_version(),
              "numpy": np.__version__, "generated_at": datetime.now(timezone.utc).isoformat()}
    (folder / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    np.savetxt(folder / "density.csv", np.asarray(result["density"]), delimiter=",")
    np.savetxt(folder / "history.csv", np.asarray(result["history"]), delimiter=",",
               header="iteration,pre_update_compliance,post_update_physical_volume,design_change", comments="")
    (folder / "description.html").write_text(description_page(PRESETS[kind], problem_description(PRESETS[kind])), encoding="utf-8")
    plot_comparison(kind, result, reference["cases"][kind], comparison, folder / "comparison.png")
    if not comparison["native_code_match"]:
        (folder / "README.md").write_text("# Reproduction to fix\n\nSee report.json for failed checks. "
                                         "Keep the target, source hash and preset settings unchanged while investigating "
                                         "loads, element ordering, filtering and stopping first.\n", encoding="utf-8")
    print(json.dumps({"case": kind, "comparison": comparison, "output": str(folder)}, indent=2))
    return comparison["native_code_match"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["all", *PRESETS], default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "results/research/top88")
    parser.add_argument("--reference", type=Path, default=FIXTURE)
    parser.add_argument("--capture-original", action="store_true")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--matlab-exe", type=Path)
    args = parser.parse_args()
    if args.capture_original:
        if args.source_dir is None or args.matlab_exe is None:
            parser.error("Capture needs --source-dir and --matlab-exe; nothing is installed or downloaded")
        report = capture_original(args.source_dir, args.matlab_exe)
        args.output.mkdir(parents=True, exist_ok=True)
        capture = args.output / "original-capture.json"
        capture.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print(capture)
        return
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    if reference["source_sha256"] != SOURCE_HASH:
        parser.error("Reference source hash differs from the reviewed top88 source")
    passed = [run_case(kind, reference, args.output) for kind in (PRESETS if args.case == "all" else [args.case])]
    if not all(passed):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
