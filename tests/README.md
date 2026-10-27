# Tests

The folders mirror the package, so the tests for a part sit where you would look for them:

| Folder | What it pins |
| :--- | :--- |
| [`golden/`](golden/) | **Characterisation tests.** Eight small runs (OC, MMA, level set, a filter chain, holes, two load cases, a 3-D cantilever) whose final designs are stored in `baselines/`. A refactor must reproduce them bit for bit; an intended change regenerates them with `python tests/golden/regenerate_baselines.py NAME` and says why in the commit. |
| [`framework/`](framework/) | Parameters and paths, JSON files and fingerprints, model + updater composition, the flat view, optimisers that run their own loop, variants (robust design). |
| [`plugins/`](plugins/) | The Q4 and H8 solvers (H8 against Q4 in the plane limit), physics engines and responses (gradients against finite differences, Q4 against pyMOTO), material laws, design representations, schedules, post-processors, 3-D, the pyMOTO backend, plugins from other packages. |
| [`engine/`](engine/) | Every analysis mode end to end on a tiny problem. |
| [`apps/`](apps/) | The command line and the GUI (run headless). |
| [`checks/`](checks/) | The conformance test: every registered plugin passes, broken ones are caught, and every example in `docs/writing-plugins.md` and `docs/quickstart.md` runs. |

Run everything with `python -m pytest`; one folder with `python -m pytest tests/plugins`.

The GUI suite parametrises Compare Methods over every registered preset. It loads
the actual panels, checks that the scenario survives unchanged (including small
loads and response defaults), and runs the automatically selected comparisons on
coarse meshes for three iterations. It checks the grid, CSV, finite metrics and
physics-specific thermal/frequency results. These are routing and execution checks,
not convergence benchmarks; the plugin tests provide the physical validation.

Test output belongs in pytest's temporary directories. `results/`, `__pycache__/`
and test/lint caches contain generated files and can be removed after a run.

Independent MATLAB observations live in [`references/matlab.json`](references/matlab.json),
separate from unchanged internal golden baselines. Three tests compare Toporia's
iteration counts and first/last compliance against unmodified top88 and top3d
to their four-decimal printed precision. Top3d's equal nodal depth forces are
matched explicitly in the reference recipe; production trapezoidal line-load
quadrature is unchanged. The fixture records original commands, hashes, runtime
and capture date. No MATLAB executable or source download is needed for these
Python regressions. See `python -m experiments.original_references --help` for
optional hash-checked original reruns using separately supplied sources.
