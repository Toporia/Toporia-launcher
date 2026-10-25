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

## Completed checkpoint: existing physics stabilised (`2dc42a1`)

The previous handoff reports 98 failures and 1686 passes. Completed:

- Use compatible objectives and load scales in the model/updater smoke tests.
- Filter updater-specific response capabilities, including local stress.
- Refuse unsupported objectives before constructing the pyMOTO vibration network.
- Keep trust-constr trial variables within their physical bounds.
- Increase its starting trust radius to 0.5: with feasible bounds, 0.1 makes
  the first step smaller than the unchanged design-change stopping tolerance.
- Use each model's load scale in response conformance checks as well as model checks.
- Update stale registry assertions while retaining numerical and golden checks.

This commit adds no new method. Test logs and temporary outputs live under ignored `results/`.

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
optional multigrid test skipped**. These were staged checks; the fresh full run
after buckling, below, now confirms the final fixes together.

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

### Completed: linearised buckling (`b9f7a7f`)

Recovered the five new files from `e081d88` into this checkout, without changing
the old worktree or rebasing its branch. Added a BUCKLING interface section and
public API exports; retained all existing physics sections. The sparse reciprocal
pencil uses a deterministic random start and shares its K factorisation with the
adjoints. Small-pencil request bounds are checked.

The initial five tests and four additional edge checks pass. Model and response
conformance pass; the response's largest gradient error is 8.3e-9. The CLI column
run on an 18 × 6 mesh converged after 104 iterations with volume 0.29995, load factor
1.02290 and a satisfied aggregate constraint. All 13 focused tests pass, including
ten buckling tests, registry assertions and GUI reachability. The fresh full suite
passes: **1918 passed, one optional multigrid test skipped**, in 43 min 18 sec.
The full log is `results/buckling-full.log`. Repository-wide Ruff and
`git diff --check` also pass. `results/buckling-validation/validation.png` plots
the coarse validation design and its measured limits; result files are not committed.

The formulation was checked against arXiv:2101.02973, especially equations 7, 10,
and 16–18. DOI 10.1007/s00158-021-02854-x is confirmed by the authors' DTU record;
Crossref itself was inaccessible from the available network tools. The code is a
paper-based implementation, with Toporia's own column and p-norm aggregate, not a
copy of the paper's MATLAB code or a reproduction of its optimisation figures.

Catalogue counts are now registry-based: 72 selectable plugins, seven underlying
physics engines, 16 presets. No implementations were removed; old totals counted
composed pairings and parameter variants as additional implementations.

### Completed: anisotropic PDE filter

Added `filters/pde_anisotropic.py` as an
independent axis-aligned Helmholtz filter with x/y/z radii. It uses conservative
cell-centred finite volumes, a symmetric monotone matrix, one cached factorisation,
and the exact adjoint. This preserves bounds at strong anisotropy and makes zero
directional radii meaningful. The original nodal-FE `pde` is unchanged; equal radii
solve the same isotropic PDE with a different discretisation.

The 25 new/existing PDE tests pass. Filter conformance passes with largest adjoint
error 1.7e-10. The CLI example (MBB, radii 3/1.5, 18 × 6 mesh, 40 iterations) is
feasible at volume 0.499927 and compliance 319.90983. All 45 focused PDE, GUI,
registry and golden tests pass. The full native suite passes: **1940 passed,
one optional multigrid test skipped**, in 31 min 05 sec
(`results/anisotropic-native-full.log`). Ruff and `git diff --check` pass.

The first anisotropic full run (`results/anisotropic-full.log`) ended without a
pytest summary at the TOBS benchmark after native CVXOPT import diagnostics,
despite using normal library settings. This is an intermittent Windows sandbox
issue, not explained by thread overrides alone. Automatic approval permitted the
same suite to run outside the sandbox, with all outputs still under `results/`.
That run completed without the diagnostic. No installed packages or global
environment settings were changed, and no dependency checks were disabled.

### Remaining sequence

1. Moving morphable voids.
2. Floating projection.
3. Simulated annealing: bounded evaluation budget; register only if conformance passes.
4. Compliant mechanism response, port springs and force-inverter preset; pyMOTO cross-check.
5. Geometry projection.
6. Reaction-diffusion level set.
7. Hamilton-Jacobi level set and topological derivative.
8. Phase field.
9. Explicit length scale, machining accessibility and projection-based self-support.
10. Multiresolution design and analysis meshes.
11. Neural reparameterisation (TOuNN), subject to dependency support on this Python/Windows setup.

Heat conduction, thermal/dynamic pyMOTO models, eigenfrequency, harmonic response,
local stress with augmented Lagrangian, and nonlinear elasticity are already
present and covered by the stabilisation milestone.

Original MATLAB/Octave reference runs remain optional, as agreed in the previous
handoff. Ask the owner before installing or changing runtimes to obtain them.
Source papers, licences, gradients, physical benchmarks, GUI reachability, CLI
examples and documentation must be checked for every addition. Never regenerate
golden baselines to accommodate a change.
