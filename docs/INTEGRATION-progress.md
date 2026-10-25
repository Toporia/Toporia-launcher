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

### Completed: moving morphable voids

Added `representations/mmv.py`: a restricted 2-D geometric dual of MMC with
one superelliptical hole per initial layout cell and five variables per hole.
Holes can translate, rotate, resize, intersect and merge. The exact adjoint
reuses MMC's tested prefix/suffix product kernel with the opposite sign; the
existing MMC implementation is unchanged. The GUI exposes the new representation.

This own paper-based variant follows the MMV principle in section 2 of
arXiv:1704.06060 (DOI 10.1016/j.cma.2017.05.002). It does not claim the paper's
3-D B-spline surfaces or FE DOF elimination. The fixed hole set and mesh-scale
lower axis bounds limit the achievable geometry; these limits are documented.

All 13 MMV tests pass, including a resolved single-hole analytic-area check,
rotated/overlapping-hole finite differences and finite gradients at saturated
overlaps. Representation conformance passes (largest relative gradient error
1.3e-7). The 60-iteration CLI MBB example reaches compliance 360.929 and volume
0.499948 against a 0.5 limit. Its geometry export contains the individual void
boundaries. `results/mmv-validation/validation.png` compares initial and final fields.

The focused run passes all 819 collected tests, covering representations, the GUI,
all plugin checks and goldens (`results/mmv-focused.log`). The analytic-area test
was added after that run was collected and passes in the 13-test MMV run. The full
native suite passes: **1955 passed, one optional multigrid test skipped**, in
26 min 33 sec (`results/mmv-native-full.log`, `results/mmv-full.xml`). Ruff and
`git diff --check` pass. No installed package or global setting was changed.
Catalogue totals are 74 selectable plugins, seven physics engines and 16 presets.

### Completed: floating projection

Added `updaters/floating_projection.py`, an own modular implementation of
Huang's damped OC ratio step and mass-preserving floating threshold. The
configured model supplies smoothing and gradient chaining; trial designs are
not smoothed again inside the updater. Volume is checked after projection,
moving limits and pinned bounds. The paper's smooth-boundary reconstruction
and reanalysis are not implemented.

Corrected a scientific error in the backlog: FPTO does use internal beta
continuation (arXiv:2006.04306, equations 16–17), unlike the old claim of no
beta continuation. Verified both DOI records on the publisher: Engineering
Structures 208 (2020) 110330 and Advances in Engineering Software 151 (2021)
102942. No source code was copied. Added a default-false updater continuation
hook, propagated through composed methods. The conformance iterate helper now
honours continuation just as the actual engine does; numerical tolerances and
the 10%-of-OC benchmark are unchanged. A regression test pins this behaviour.

All 11 new tests pass, including 2-D/3-D projection mass preservation, pinned
values, weighted volume, move limits, staged continuation and the benchmark.
Conformance gives compliance 276.884 vs OC 274.470 (+0.9%), volume 0.500.
With the shared default move 0.2 it finishes in 60 iterations, with design
greyness mean(4*x*(1-x)) = 0.00522; physical boundaries remain filtered.
The documented CLI example uses move 0.02 and stops at iteration 128 after
actually using beta 8. Its optimiser report explicitly confirms completed
continuation (`results/floating-validation`, `results/floating-cli.log`).

All 1289 focused regression tests pass, including framework composition, GUI,
plugin conformance, guide examples and goldens (`results/floating-focused.log`,
`results/floating-focused.xml`). The full native suite passes: **2021 passed,
one optional multigrid test skipped**, in 26 min 01 sec, with workspace-local
temporary files (`results/floating-native-full.log`, `results/floating-full.xml`).
Ruff and `git diff --check` pass. Catalogue totals are 75 selectable plugins,
seven physics engines and 16 presets; 23 updaters form 230 named model pairings.

### Completed evaluation: simulated annealing (not registered)

Added `experiments/simulated_annealing.py` as an isolated, reproducible standard
Metropolis baseline, not a selectable plugin. The referenced topASA repository
has no stated licence; no source code was copied and these measurements do not
evaluate adaptive topASA. The own implementation uses random pair transfers,
geometric cooling and scalar physical-volume repair, with no physics gradients.
Budgets include the initial solve; the best feasible state is retained.

On the unchanged 24 × 8 MBB conformance mesh, OC reaches compliance 274.46963
in 57 solves including final evaluation. SA at 200 solves gives 794.173,
809.155 and 816.480 for seeds 0/1/2 (+189–197%). At 2000 solves the values
are 380.895, 391.319 and 393.244 (+39–43%). All are within the volume budget;
none reaches the existing 10%-of-OC gate. Accordingly, no updater is registered
and no benchmark or numerical tolerance is weakened. Detailed method, caveats,
command and table are in `experiments/README.md`; raw outputs are under
`results/annealing-evaluation/` and `results/annealing-evaluation.log`.

Eight new experiment tests pass (budget, no gradients, deterministic seed,
best history, bounds and pins, invalid controls, absence from registry).
Repository-wide Ruff and whitespace checks pass. No registered/runtime plugin
changed since the full-suite checkpoint of 2021 passes and one optional skip;
only this isolated experiment and its tests were run for the evaluation.
Implementation counts remain unchanged.

### Remaining sequence

1. Compliant mechanism response, port springs and force-inverter preset; pyMOTO cross-check.
2. Geometry projection.
3. Reaction-diffusion level set.
4. Hamilton-Jacobi level set and topological derivative.
5. Phase field.
6. Explicit length scale, machining accessibility and projection-based self-support.
7. Multiresolution design and analysis meshes.
8. Neural reparameterisation (TOuNN), subject to dependency support on this Python/Windows setup.

Heat conduction, thermal/dynamic pyMOTO models, eigenfrequency, harmonic response,
local stress with augmented Lagrangian, and nonlinear elasticity are already
present and covered by the stabilisation milestone.

Original MATLAB/Octave reference runs remain optional, as agreed in the previous
handoff. Ask the owner before installing or changing runtimes to obtain them.
Source papers, licences, gradients, physical benchmarks, GUI reachability, CLI
examples and documentation must be checked for every addition. Never regenerate
golden baselines to accommodate a change.
