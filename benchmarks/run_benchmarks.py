"""
Canonical topology-optimisation benchmarks.

Run from the repository root:
    python benchmarks/run_benchmarks.py

Each benchmark runs to convergence at the reference settings and reports:
  - final compliance (objective value)
  - final volume fraction
  - iterations taken
  - pass/fail against expected compliance tolerance

Reference values match the classic top88 MATLAB code (Andreassen et al. 2011)
for the density method with a density filter (rmin=1.5, penal=3, OC update).
"""

import sys
import time
from pathlib import Path

# Allow running directly: python benchmarks/run_benchmarks.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from toporia.core.config import TopOptConfig, LoadCase, EdgeConstraint, PointConstraint, PointLoad
from toporia.core.runner import run_single
from toporia.problems    import get_config


# ── Benchmark definitions ─────────────────────────────────────────────────────

BENCHMARKS = [
    {
        "name": "MBB Beam",
        "problem": "MBB Beam",
        # top88 reference: nelx=60, nely=20, volfrac=0.5, penal=3, rmin=1.5
        # Expected compliance ≈ 188 (OC update, density filter, F=1)
        "expected_compliance": 188.0,
        "tolerance_pct": 5.0,   # accept ±5 % of expected
    },
    {
        "name": "Cantilever",
        "problem": "Cantilever",
        # Lx=60, Ly=30, volfrac=0.4, penal=3, rmin=1.5, downward tip load
        # No published canonical value — tolerance is loose.
        "expected_compliance": None,
        "tolerance_pct": None,
    },
    {
        "name": "Three-Point Bending",
        "problem": "Three-Point Bending",
        "expected_compliance": None,
        "tolerance_pct": None,
    },
    {
        "name": "Drone Arm",
        "problem": "Drone Arm",
        "expected_compliance": None,
        "tolerance_pct": None,
    },
]


# ── Runner ────────────────────────────────────────────────────────────────────

def _run_one_benchmark(spec: dict) -> dict:
    cfg = get_config(spec["problem"])
    t0  = time.perf_counter()
    density = run_single(cfg)
    elapsed = time.perf_counter() - t0

    from toporia.core.problem import RectangularProblem
    from toporia.methods.base import solve_fea
    _, _, compliance = solve_fea(RectangularProblem(cfg), cfg, density)

    volfrac = float(density.mean())
    return {
        "name":       spec["name"],
        "compliance": compliance,
        "volfrac":    volfrac,
        "elapsed_s":  elapsed,
        "expected":   spec["expected_compliance"],
        "tol_pct":    spec["tolerance_pct"],
    }


def _check(result: dict) -> str:
    if result["expected"] is None:
        return "SKIP (no reference)"
    diff_pct = abs(result["compliance"] - result["expected"]) / result["expected"] * 100
    if diff_pct <= result["tol_pct"]:
        return f"PASS  (diff {diff_pct:.1f}%)"
    return f"FAIL  (diff {diff_pct:.1f}%, expected {result['expected']:.1f})"


def run_all(verbose: bool = True) -> list[dict]:
    results = []
    for spec in BENCHMARKS:
        if verbose:
            print(f"\n{'─'*60}")
            print(f"  {spec['name']}")
            print(f"{'─'*60}")
        r = _run_one_benchmark(spec)
        r["status"] = _check(r)
        results.append(r)
        if verbose:
            print(f"  compliance = {r['compliance']:.4f}")
            print(f"  volfrac    = {r['volfrac']:.4f}")
            print(f"  time       = {r['elapsed_s']:.1f}s")
            print(f"  status     = {r['status']}")
    return results


def _summary(results: list[dict]):
    print(f"\n{'═'*60}")
    print("  BENCHMARK SUMMARY")
    print(f"{'═'*60}")
    for r in results:
        print(f"  {r['name']:<30}  {r['status']}")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    results = run_all(verbose=True)
    _summary(results)
    any_fail = any("FAIL" in r["status"] for r in results)
    sys.exit(1 if any_fail else 0)
