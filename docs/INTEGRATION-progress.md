# Integration progress

Work is confined to `toporia-integration`, on `integration/physics`. The owner
reviews and merges into the release; the GUI and launcher source checkouts are
not changed here. Work proceeds sequentially, with a separate commit for each
new method, including its documentation and validation.

## Scope agreed 25 October 2026

The small and medium lists on page 7 of `Toporia-library.pdf` are the scope.
The PDF predates the latest physics integrations. Already implemented items
are validated and repaired rather than implemented again. Large framework
projects, datasets, and other backlog items are outside this round.

## Current checkpoint: existing physics stabilised

The previous handoff reports 98 failures and 1686 passes. Completed:

- Use compatible objectives and load scales in the model/updater smoke tests.
- Filter updater-specific response capabilities, including local stress.
- Refuse unsupported objectives before constructing the pyMOTO vibration network.
- Keep trust-constr trial variables within their physical bounds.
- Increase its starting trust radius to 0.5: with feasible bounds, 0.1 makes
  the first step smaller than the unchanged design-change stopping tolerance.
- Use each model's load scale in response conformance checks as well as model checks.
- Update stale registry assertions while retaining numerical and golden checks.

No new method has been added yet. Next is buckling. Test logs and temporary outputs
live under ignored `results/`.

### Validation

- Broad run: 1732 passed, 43 skipped, 12 failed, in 38 min 51 sec.
  The entire GUI suite and all golden comparisons passed.
- All 12 failures passed on rerun after correcting the trust radius and temporary
  directory settings (`results/integration-recheck.log`).
- The 42 unsupported-pair skips were replaced with assertions that the engine
  rejects these combinations; all 42 passed (`results/incompatible-checks.log`).
- All 22 targeted trust-constr tests passed, including the unchanged OC benchmark
  and every model pairing (`results/trust-final.log`). Radius 0.5 reaches compliance
  278.5 against OC's 274.5 (about +1.5%).
- Repository-wide Ruff and `git diff --check` passed.

Coverage across the broad run and targeted reruns: **1786 passing tests and one
optional multigrid test skipped**. This is not a claim of a fresh, single-command
full-suite pass after the final fixes. The next full run must use the settings below.

### Running tests in this Windows sandbox

Use the normal numerical-library environment. A run with thread-count overrides
emitted native CVXOPT import diagnostics and ended without a pytest summary;
installed packages were not changed.

The sandbox's default temporary directory can be created but cannot always be
cleaned up. Set both `TEMP` and `TMP` to an existing `results/tmp` directory in
this checkout, and also pass `--basetemp=results/pytest-full` to pytest. These are
process-local settings, not changes to Windows or the application.

Use the Python 3.14 executable from the handoff, with:
`python -u -m pytest -vv --tb=short --durations=15 --basetemp=results/pytest-full`.
The broad-run log is `results/integration-full-default.log`; earlier interrupted
or partial logs are not evidence of a full-suite pass.

## Sequential queue after stabilisation

1. Recover and validate the existing untested linearised buckling implementation.
2. Anisotropic PDE filter.
3. Moving morphable voids.
4. Floating projection.
5. Simulated annealing: bounded evaluation budget; register only if conformance passes.
6. Compliant mechanism response, port springs and force-inverter preset; pyMOTO cross-check.
7. Geometry projection.
8. Reaction-diffusion level set.
9. Hamilton-Jacobi level set and topological derivative.
10. Phase field.
11. Explicit length scale, machining accessibility and projection-based self-support.
12. Multiresolution design and analysis meshes.
13. Neural reparameterisation (TOuNN), subject to dependency support on this Python/Windows setup.

Heat conduction, thermal/dynamic pyMOTO models, eigenfrequency, harmonic response,
local stress with augmented Lagrangian, and nonlinear elasticity are already
present and covered by the stabilisation milestone.

Original MATLAB/Octave reference runs remain optional, as agreed in the previous
handoff. Ask the owner before installing or changing runtimes to obtain them.
Source papers, licences, gradients, physical benchmarks, GUI reachability, CLI
examples and documentation must be checked for every addition. Never regenerate
golden baselines to accommodate a change.
