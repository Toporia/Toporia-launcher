# Tests

The folders mirror the package, so the tests for a part sit where you would look for them:

| Folder | What it pins |
| :--- | :--- |
| [`golden/`](golden/) | **Characterisation tests.** Seven small runs (OC, MMA, level set, a filter chain, holes, two load cases) whose final designs are stored in `baselines/`. A refactor must reproduce them bit for bit; an intended change regenerates them with `python tests/golden/regenerate_baselines.py NAME` and says why in the commit. |
| [`framework/`](framework/) | Parameters and paths, JSON files and fingerprints, model + updater composition, the flat view, optimisers that run their own loop. |
| [`plugins/`](plugins/) | The Q4 solver, physics engines and responses (gradients against finite differences, Q4 against pyMOTO), objectives and constraints, the pyMOTO backend, plugins from other packages. |
| [`engine/`](engine/) | Every analysis mode end to end on a tiny problem. |
| [`apps/`](apps/) | The command line and the GUI (run headless). |
| [`checks/`](checks/) | The conformance test: every registered plugin passes, broken ones are caught, and every example in `docs/writing-plugins.md` runs. |

Run everything with `python -m pytest`; one folder with `python -m pytest tests/plugins`.
