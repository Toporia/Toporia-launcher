"""Reproduce the Python side of captured, unmodified MATLAB reference runs.

Default: python -m experiments.original_references
Optional original rerun: --matlab --source-dir PATH [--matlab-exe PATH]
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matlab", action="store_true")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--matlab-exe", default=shutil.which("matlab"))
    args = parser.parse_args()
    reference = json.loads(REFERENCES.read_text(encoding="utf-8"))
    if args.matlab:
        if args.source_dir is None or not args.matlab_exe:
            parser.error("MATLAB reruns need --source-dir and an available --matlab-exe")
        results = rerun_matlab(reference, args.source_dir, args.matlab_exe)
    else:
        results = [validate(case) for case in reference["cases"]]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
