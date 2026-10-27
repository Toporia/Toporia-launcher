"""Reproduce the Python side of captured, unmodified MATLAB reference runs.

Default: python -m experiments.original_references
Optional original rerun: --matlab --source-dir PATH [--matlab-exe PATH]
Read-only runtime/helper audit: --audit-matlab [--matlab-exe PATH]
Optional mmapy comparison against the captured native optimizer: --mma
Download the two sources linked in tests/references/matlab.json into PATH.
Their bytes must match the recorded hashes. No download, install, source
patch, MATLAB path save or fixture update is performed by this recipe.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from toporia.framework import LoadCase, PointLoad
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.methods import method_class
from toporia.plugins.problems import get_run

REFERENCES = Path(__file__).resolve().parents[1] / "tests" / "references" / "matlab.json"


def validate_mma():
    """Compare the optional mmapy port on the captured convex reciprocal problem.

    Minimize sum(w/x) subject to sum(x)<=2.4, 0.05<=x<=1. The unconstrained
    initial design is deliberately over budget. The interior optimum is
    x=2.4*sqrt(w)/sum(sqrt(w)); all native MMA defaults are retained.
    """
    from mmapy.mma import mmasub

    n = 6
    weights = np.array([1., 2., 3., 5., 7., 11.]).reshape(-1, 1)
    target = 2.4
    x = np.linspace(.25, .75, n).reshape(-1, 1)
    xmin, xmax = np.full_like(x, .05), np.ones_like(x)
    old1, old2, low, upp = x.copy(), x.copy(), xmin.copy(), xmax.copy()
    report = {"initial_objective": float(np.sum(weights/x))}
    for iteration in range(1, 31):
        result = mmasub(1, n, iteration, x, xmin, xmax, old1, old2,
                        float(np.sum(weights/x)), -weights/x**2,
                        np.array([[x.sum()/target-1]]), np.ones((1, n))/target,
                        low, upp, 1., np.zeros((1, 1)), np.full((1, 1), 1000.), np.zeros((1, 1)))
        old2, old1, x = old1, x.copy(), result[0]
        low, upp = result[-2:]
        if iteration == 1:
            report["first_design"] = x.ravel().tolist()
    report.update(iterations=iteration, final_design=x.ravel().tolist(),
                  final_objective=float(np.sum(weights/x)), final_budget=float(x.sum()),
                  final_multiplier=float(result[3].item()))
    return report


def validate(case):
    if case["name"].startswith("top88"):
        kind = "sensitivity" if case["name"].endswith("sensitivity") else "density"
        run = get_run("MBB Beam").updated(method="q4+oc", m=.4,
                                         filter_specs=[{"type": kind, "rmin": 1.5}])
    else:
        run = get_run("Cantilever").updated(
            method="h8+oc", Lx=12, Ly=4, Lz=2, m=1., volfrac=.3,
            point_loads=[PointLoad(12, 0)], load_cases=[LoadCase(Fmag=3., Fa=270., weight=1.)],
            filter_specs=[{"type": "density", "rmin": 1.5}])
    problem = make_problem(run.scenario, run.solver.m)
    if len(problem.shape) == 3:
        # Match top3d's discrete point forces exactly. Production line-load
        # trapezoidal integration remains untouched and is a different load.
        problem.layer_weights = np.full(problem.nelz+1, 1/(problem.nelz+1))
    method = method_class(run.solver.method)()
    method.initialize(problem, run.solver)
    first = None
    for iteration in range(1, 201):
        method.step(iteration)
        if first is None:
            first = method.get_responses()["objective"]
        if method.get_change() < .01:
            break
    result = {"name": case["name"], "iterations": iteration, "first_reported_compliance": first,
              "last_reported_compliance": method.get_responses()["objective"],
              "final_mean_density": float(method.get_density().mean()), "last_change": method.get_change()}
    method.close()
    return result


def rerun_matlab(reference, source_dir, executable):
    """Read only supplied originals; isolate all graphics and outputs in a temp directory."""
    with tempfile.TemporaryDirectory(prefix="toporia-matlab-reference-") as temporary:
        scratch = Path(temporary)
        for name, source in reference["sources"].items():
            supplied = source_dir / name
            if hashlib.sha256(supplied.read_bytes()).hexdigest() != source["sha256"]:
                raise ValueError(f"Source hash changed: {name}; review it before running")
            shutil.copyfile(supplied, scratch / name)
        commands = ";".join("'"+case["command"].replace("'", "''")+"'" for case in reference["cases"])
        script = "set(groot,'defaultFigureVisible','off');\ncommands={"+commands+"};\n"
        script += """report.runtime=version;
for i=1:numel(commands)
  output=evalc(commands{i});
  tokens=regexp(output,'It.:\\s*(\\d+)\\s+Obj.:\\s*([\\d.eE+-]+)\\s+Vol.:\\s*([\\d.eE+-]+)\\s+ch.:\\s*([\\d.eE+-]+)','tokens');
  assert(~isempty(tokens),'No iteration output'); first=tokens{1}; last=tokens{end};
  item.command=commands{i}; item.iterations=str2double(last{1});
  item.first_reported_compliance=str2double(first{2});
  item.last_reported_compliance=str2double(last{2});
  item.reported_volume=str2double(last{3}); item.reported_change=str2double(last{4});
  report.cases(i)=item; close all force;
end
fid=fopen('report.json','w'); fprintf(fid,'%s',jsonencode(report)); fclose(fid);
"""
        (scratch / "capture.m").write_text(script, encoding="utf-8")
        completed = subprocess.run([executable, "-batch", "run('capture.m');"], cwd=scratch,
                                   capture_output=True, text=True, timeout=900, check=False)
        if completed.returncode:
            raise RuntimeError(f"MATLAB reference run failed:\n{completed.stdout}\n{completed.stderr}")
        report = json.loads((scratch / "report.json").read_text(encoding="utf-8"))
        # MATLAB encodes a one-element struct array as a JSON object.
        if isinstance(report.get("cases"), dict):
            report["cases"] = [report["cases"]]
        return report


def audit_matlab(executable):
    """Inspect the current runtime; never set a path, select a compiler or install helpers."""
    with tempfile.TemporaryDirectory(prefix="toporia-matlab-audit-") as temporary:
        scratch = Path(temporary)
        script = """report.runtime=version;
report.optimization_toolbox_licensed=logical(license('test','Optimization_Toolbox'));
names={'fsparse','mmasub','subsolv','MMC188','top_levelset','levelset88','intlinprog'};
for i=1:numel(names), report.helpers.(names{i})=which(names{i}); end
try
  selected=mex.getCompilerConfigurations('C','Selected');
  report.c_compiler_selected=~isempty(selected);
  if isempty(selected), report.c_compiler_name='';
  else, report.c_compiler_name=selected(1).Name; end
catch error
  report.c_compiler_selected=false; report.compiler_audit_error=error.message;
end
fid=fopen('report.json','w'); fprintf(fid,'%s',jsonencode(report)); fclose(fid);
"""
        (scratch / "audit.m").write_text(script, encoding="utf-8")
        completed = subprocess.run([executable, "-batch", "run('audit.m');"], cwd=scratch,
                                   capture_output=True, text=True, timeout=300, check=False)
        if completed.returncode:
            raise RuntimeError(f"MATLAB audit failed:\n{completed.stdout}\n{completed.stderr}")
        return json.loads((scratch / "report.json").read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--matlab", action="store_true")
    mode.add_argument("--audit-matlab", action="store_true")
    mode.add_argument("--mma", action="store_true")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--matlab-exe", default=shutil.which("matlab"))
    args = parser.parse_args()
    reference = json.loads(REFERENCES.read_text(encoding="utf-8"))
    if args.mma:
        results = validate_mma()
    elif args.audit_matlab:
        if not args.matlab_exe:
            parser.error("The runtime audit needs an available --matlab-exe")
        results = audit_matlab(args.matlab_exe)
    elif args.matlab:
        if args.source_dir is None or not args.matlab_exe:
            parser.error("MATLAB reruns need --source-dir and an available --matlab-exe")
        results = rerun_matlab(reference, args.source_dir, args.matlab_exe)
    else:
        results = [validate(case) for case in reference["cases"]]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
