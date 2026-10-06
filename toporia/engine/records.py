# engine/records.py — what every run leaves behind.
#
# Three things, in the order the loop uses them:
#
#   ResultStore     the history while the run goes (objective, volume, every
#                   reported response, per iteration), density snapshots, and
#                   at the end final_density.png, final_density.csv and,
#                   for an interactive run, history.png
#   check_limits    whether the final design honours every limit
#   run_record      run.json: what was solved, how, which parts and which code
#                   (with the package and version of every plugin), how it ended
#
#     loop ──record()──> ResultStore ──save_final()──> PNG, CSV
#       └──final responses──> check_limits ──> WARNING lines ─┐
#                                                             └──> run_record ──> run.json

import csv
import functools
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import scipy
from PIL import Image  # writes the greyscale PNGs

import toporia
from toporia.framework.problem.files import dump_json, fingerprint, to_dict
from toporia.framework.problem.mesh import projection
from toporia.framework.problem.run import PROJECT_ROOT

# ── The history and the images ────────────────────────────────────────────────
#
# ResultStore is created once per run.  The optimisation loop calls record()
# after every iteration, and save_final() when converged.
# It writes three types of files into the run's output folder:
#   density_NNNN.png   — greyscale density snapshot every save_every iterations
#   final_density.png  — the converged design
#   history.png        — objective and volume fraction plotted against iteration

class ResultStore:
    """One run's history and output files.  The loop calls record() every iteration and save_final() at the end."""
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)  # create folder if needed
        self.objectives = []   # objective value recorded each iteration
        self.volumes    = []   # mean density (= material fraction) each iteration
        self.responses  = {}   # name -> per-iteration list, for every response a
                               # method reports (constraint values, beta, ...)
        self.stop_reason = None  # set by the runner when the loop ends
        self.postprocess = {}    # what the post-processors made of the final design

    def record(self, iteration, objective, volume, density, save_every=0, responses=None):
        """Append one iteration's data and optionally save a density snapshot."""
        self.objectives.append(float(objective))
        self.volumes.append(float(volume))
        # Methods may report any number of extra scalars; keep them all so the
        # comparison engine can plot more than compliance without a contract change.
        for name, value in (responses or {}).items():
            self.responses.setdefault(name, []).append(float(value))
        # save_every=0 means disabled; otherwise save when iteration is a multiple
        if save_every and iteration % save_every == 0:
            self.save_density(density, self.output_dir / f"density_{iteration:04d}.png")

    def save_final(self, density, save_history=True):
        """Write the final density image, CSV, and optionally the history plot.

        A 3-D design is drawn and written to the CSV as its average through the
        depth (framework/problem/mesh.py, projection), and saved whole as
        final_density.npy.
        """
        self.save_density(density, self.output_dir / "final_density.png")
        self.save_csv(projection(density))
        if np.ndim(density) == 3:
            np.save(self.output_dir / "final_density.npy", np.asarray(density))
        if save_history:
            self.save_history()

    def save_json(self, name, data):
        """Write a JSON document — such as the run.json provenance record — to the output folder."""
        (self.output_dir / name).write_text(dump_json(data) + "\n", encoding="utf-8")

    def save_csv(self, density):
        """Write final_density.csv: two metadata rows then the density matrix.

        Row 1 — iterations taken
        Row 2 — final objective value
        Rows 3+ — density matrix (row 0 = top of image, matching the PNG orientation)
        Each value is the material density [0, 1] of that finite element.
        """
        density_out = np.flipud(density)   # row 0 = image top, matching final_density.png
        with open(self.output_dir / "final_density.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["iterations", len(self.objectives)])
            writer.writerow(["objective",  f"{self.objectives[-1]:.6g}"])
            for row in density_out:
                writer.writerow([f"{v:.4f}" for v in row])

    def save_density(self, density, path):
        """Convert a float density array to an 8-bit greyscale PNG.

        Steps:
          1. flipud  — flip vertically so row 0 appears at the bottom of the image
          2. 1-density — invert so solid (density≈1) is dark and void (≈0) is light
          3. ×255    — scale to byte range [0, 255]
          4. clip    — guard against any values that slipped outside [0,1]
        """
        pixels = np.flipud(1.0 - projection(density))
        pixels = (np.clip(pixels, 0.0, 1.0) * 255).astype(np.uint8)
        Image.fromarray(pixels, mode="L").save(path)   # "L" = 8-bit greyscale

    def save_history(self):
        """Write a two-panel PNG: objective (top) and volume fraction (bottom)."""
        fig, axes = plt.subplots(2, 1, figsize=(6, 5), sharex=True)  # shared x-axis
        axes[0].plot(self.objectives); axes[0].set_ylabel("Objective")
        axes[1].plot(self.volumes);    axes[1].set_ylabel("Volume")
        axes[1].set_xlabel("Iteration")
        fig.tight_layout()
        fig.savefig(self.output_dir / "history.png", dpi=160)
        plt.close(fig)   # close so the figure is not shown as an interactive window


# ── Did the result honour its limits? ─────────────────────────────────────────
#
# An optimiser that cannot satisfy every limit at once does not stop with an
# error: it settles on a compromise.  Asked for a stress limit that cannot be
# met within the volume budget, MMA meets the stress limit and quietly uses
# more material than allowed.  Such a result looks like any other unless
# someone reads the constraint values in the history.
#
# So after every run the engine checks each limit explicitly — the volume
# budget, which every method enforces, and every scenario constraint — prints
# a warning for each one that is broken, and records the verdict in run.json.
# Constraints are judged on their exact value when the method reports one
# (the true peak stress, not the p-norm standing in for it).

TOLERANCE = 0.01


def check_limits(scenario, responses):
    """Return one entry per limit: {"name", "value", "limit", "satisfied"}.

    `responses` is a method's final responses dict.  A constraint the method
    did not report is listed with "satisfied": None rather than guessed.
    """
    report = []
    volume = responses.get("volume")
    if volume is not None:
        report.append({
            "name": "volume budget",
            "value": float(volume),
            "limit": scenario.volfrac,
            "satisfied": bool(volume <= scenario.volfrac * (1 + TOLERANCE)),
        })

    for i, spec in enumerate(scenario.constraints):
        key = f"constraint_{i}_{spec.get('type')}"
        g = responses.get(f"{key}_exact", responses.get(key))
        name = f"constraint {i + 1} ({spec.get('type')})"
        if g is None:
            report.append({"name": name, "value": None, "limit": spec.get("limit"), "satisfied": None})
            continue
        # Constraints are normalised as value / limit − 1; show them in the
        # user's units when the spec has a limit.
        limit = spec.get("limit")
        value = (1.0 + g) * limit if limit is not None else g
        report.append({
            "name": name,
            "value": float(value),
            "limit": limit if limit is not None else 0.0,
            "satisfied": bool(g <= TOLERANCE),
        })
    return report


def describe_violations(report):
    """One readable line per broken limit; empty when every limit is met."""
    lines = []
    for entry in report:
        if entry["satisfied"] is False:
            over = entry["value"] / entry["limit"] - 1.0 if entry["limit"] else None
            amount = f" ({over:.1%} over)" if over is not None else ""
            lines.append(f"{entry['name']} not met: {entry['value']:.4g} against a limit of "
                         f"{entry['limit']:.4g}{amount}")
    return lines


# ── run.json: what produced the result ────────────────────────────────────────
#
# Every run writes run.json into its output directory: the exact scenario and
# solver (in full, plus a short fingerprint of each), the software versions and
# git commit, and how the run ended.
#
# Two results with the same scenario fingerprint were solved on the same
# problem; two with the same solver fingerprint were solved the same way.  That
# is what makes a comparison reproducible and citable.

@functools.lru_cache(maxsize=1)
def _git_state():
    """Commit and dirty flag of the Toporia checkout, or None outside a git repo."""
    def git(*args):
        """Run one git command in the checkout and return its output."""
        return subprocess.run(["git", "-C", str(PROJECT_ROOT), *args],
                              capture_output=True, text=True, timeout=5, check=True).stdout.strip()
    try:
        return {
            "commit": git("rev-parse", "HEAD"),
            # Untracked files (such as results/) do not change what code ran.
            "dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        }
    except (OSError, subprocess.SubprocessError):
        return None


def software():
    """Versions of everything that can change a result."""
    return {
        "toporia": toporia.__version__,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "platform": platform.platform(),
        "git": _git_state(),
    }


def parts_record(run):
    """Every plugin the run used: what it is, which package it came from, and the versions.

    A result made with a plugin from another package can only be reproduced
    with that package at that version, so both are recorded, together with
    the versions of the optional packages the plugin declares it needs.
    """
    from importlib import metadata

    from toporia.engine.pipeline import part_origin, pipeline_parts

    def version_of(package):
        try:
            return metadata.version(package)
        except (metadata.PackageNotFoundError, ValueError):
            return None

    record = []
    for kind, cls in pipeline_parts(run):
        entry = {"kind": kind, "name": cls.name, "label": cls.label,
                 "class": f"{cls.__module__}.{cls.__qualname__}", **part_origin(kind, cls)}
        dependencies = getattr(cls, "dependencies", ())
        if dependencies:
            entry["dependencies"] = {name: version_of(name) for name in dependencies}
        record.append(entry)
    return record


def run_record(run, *, iterations, stop_reason, responses, limits=(), optimiser=None, postprocess=None):
    """The provenance document written as run.json at the end of every run.

    `limits` is check_limits' report; `feasible` is False
    when any limit is known to be broken.  `optimiser` is the optimiser's own
    verdict (method.report()), for libraries that run their own loop: their
    success flag, message and counts sit next to Toporia's stop reason.
    """
    record = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "software": software(),
        "scenario": {"fingerprint": fingerprint(run.scenario), "definition": to_dict(run.scenario)},
        "solver": {"fingerprint": fingerprint(run.solver), "definition": to_dict(run.solver)},
        "parts": parts_record(run),
        "result": {
            "iterations": iterations,
            "stop_reason": stop_reason,
            "feasible": all(entry["satisfied"] is not False for entry in limits),
            "limits": list(limits),
            "final": responses,
        },
    }
    if optimiser:
        record["result"]["optimiser"] = optimiser
    if postprocess:
        record["postprocess"] = postprocess
    return record
