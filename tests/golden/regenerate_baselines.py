"""regenerate_baselines.py — (re)write the stored golden baselines.

Run this ONLY when a behaviour change is intentional, and commit the resulting
.npz files in the same commit as the change so the diff shows both.

    python tests/golden/regenerate_baselines.py            # all cases
    python tests/golden/regenerate_baselines.py mbb_oc     # one case
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # the repository root

from tests.golden._harness import run_case  # noqa: E402
from tests.golden.cases import CASES  # noqa: E402

BASELINE_DIR = Path(__file__).resolve().parent / "baselines"


def main(names):
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    scratch = BASELINE_DIR / "_scratch"
    for name in names:
        result = run_case(CASES[name](), scratch)
        np.savez_compressed(BASELINE_DIR / f"{name}.npz", **result)
        print(f"  {name:16s} obj={float(result['objective']):12.6f} "
              f"it={int(result['iterations']):3d} shape={result['density'].shape}")
    print(f"\nWrote {len(names)} baseline(s) to {BASELINE_DIR}")


if __name__ == "__main__":
    requested = sys.argv[1:] or list(CASES)
    unknown = [n for n in requested if n not in CASES]
    if unknown:
        raise SystemExit(f"Unknown case(s): {unknown}\nAvailable: {list(CASES)}")
    main(requested)
