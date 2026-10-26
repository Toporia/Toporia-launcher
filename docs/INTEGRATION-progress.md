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

### Completed: compliant mechanism and force inverter

Added a separate Q4 mechanism physics/model and signed output-displacement
response. `Scenario.point_springs` describes density-independent x/y ground
springs. Only spring-capable models accept them; ordinary models and whole
methods reject such scenarios instead of silently ignoring the springs.
The original Q4 and H8 solver sources are unchanged. One augmented stiffness
factorisation serves real loads and adjoints; compliance includes spring energy.
Point probes remain opaque to the response, so it does not index backend DOFs.
The stable API exports the new displacement feature and interface.

The Force Inverter preset uses Toporia's own 40 × 40 domain, corner supports,
input/output springs 0.01, force 0.001 and output in the -x direction. It is
based on Sigmund's 1997 formulation, not a reproduction of its figures. Springs
round-trip through JSON and support indexed CLI parameter paths. The existing
integration GUI preserves them and draws springs plus the desired output arrow;
the separate GUI worktree is untouched.

The initial thirteen mechanism tests pass, including multi-case density gradients with
springs, spring/material energy balance, zero-spring equivalence, linear force
scaling, signed output and a passive-energy transfer bound. The optional
independent pyMOTO FE assembly and automatic gradient agree. Native model and
response conformance pass (largest relative errors 1.4e-6 and 3.1e-8). The first
16 × 16 CLI example stopped at iteration 111 with objective -0.0258618, meaning
output motion 0.0258618 in the desired direction, at volume 0.399998.
Two additional spring-only support tests pass: no invented clamp, reaction
balance, and rejection of residual rigid motion. The GUI round trip and preview
tests pass. Documentation and registry assertions are updated; totals are 77
selectable parts, eight physics engines and 17 presets. The documented CLI
example was rerun successfully in `results/mechanism-validation/`.

Focused native regressions completed with 1780 passes and one failure: the
new preset used integer coordinates, which JSON reload normalised to floats,
changing its fingerprint despite numerical equality. Corrected preset types
and normalised numeric fields in the new PointSpring constructor. The 40-test
repair run passes, including all preset round trips and the mechanism/GUI
checks (`results/mechanism-serialization-repair.xml`). No assertion or
fingerprint algorithm was weakened. The CLI was rerun with corrected metadata.

The fresh full native suite passes: **2173 passed, one optional multigrid test
skipped**, in 26 min 07 sec (`results/mechanism-native-full.log`,
`results/mechanism-full.xml`), with all temporary files inside `results/`.
Repository-wide Ruff and whitespace checks pass. The original Q4 and H8
element sources and golden baselines remain unchanged.
`results/mechanism-validation/validation.png` shows the verified problem and
coarse design. No later method was started during this validation.

### Completed: geometry projection

Added `representations/geometry_projection.py`, an independently implemented
2-D/3-D fixed-radius capsule family with floating endpoints and component
activation. The local circular/spherical-cap projection uses signed distance;
a bounded product joins components. Volume uses the unpenalised field and the
configured material law penalises the combined density. These modular choices
differ from GPTO's per-component penalty and p-norm. No original code is copied:
the Smith/Norato 2020 paper states GPTO's code licence is CC-BY-NC 4.0. The
2015 CMAME and 2020 SMO DOI records and the open-access formulation were verified.

The cap is a local flat-interface approximation, not an exact ball/capsule
intersection at curved ends. Bars have a fixed stock radius that must cover
the sample window, and their fixed initial set cannot nucleate new bars.
Collapsed segments have finite averaged endpoint subgradients, not classical
derivatives in every direction. Shared endpoints, stacked thickness and general
non-capsule feature families are not implemented. These limits are documented.

All 19 new tests pass: independent disk/sphere cross-section integration,
analytic capsule area/volume, all endpoint and activation derivatives in both
dimensions, endpoint reversal, zero activation, collapse/overlap handling,
invalid controls, an H8 integration run, and a feasible geometric MBB example.
Representation conformance passes (largest gradient error 1.5e-6). The CLI
example uses no extra density filter and reports compliance 212.942, volume
0.499504 at its 150-iteration cap. This is not a convergence claim or a
like-for-like comparison against default filtered OC.

Documentation, registry assertions and counts are updated: 78 selectable
plugins, eight physics engines and 17 presets. Ruff and whitespace checks pass.
All 916 focused native regressions pass (`results/geometry-projection-focused.log`,
`results/geometry-projection-focused.xml`), covering representations, GUI,
plugin conformance, guide examples and goldens. The full native suite passes:
**2194 passed, one optional multigrid test skipped**, in 26 min 34 sec
(`results/geometry-projection-native-full.log`, `results/geometry-projection-full.xml`).
Ruff and whitespace checks pass. The inspected
`results/geometry-projection-validation/validation.png` distinguishes physical
density from nominal outlines, which do not encode fractional activation.
No later method was started during validation.

### Completed: reaction-diffusion level set

Added `methods/levelset_reaction_diffusion.py`, an independent sparse,
cell-centred, 2-D compliance variant after Otomori et al. (2015), DOI
10.1007/s00158-014-1190-z. No original MATLAB code is copied. The publisher's
public Appendix C supplies the in-plane elastic tensor. It is the paper's
reduction of a spherical-cavity tensor, not a circular-hole asymptotic
derivative or ordinary SIMP gradient. The tensor is independently checked on
affine strains, nonsquare cells, several Poisson ratios and rigid motions.

Positive bounded phi describes solid; a cubic Heaviside gives material
fractions and linear ersatz stiffness. All-domain reaction permits nucleation
from full solid. Implicit no-flux finite-volume diffusion has a physical-mm
length parameter. One sparse factorisation and its response to constant
forcing permit bisection of the new volume without repeated FE solves. This
volume controller replaces the original augmented-Lagrangian feedback. No
reinitialisation, dense RBF or automatic mesh coarsening is used. Fixed regions
are Dirichlet values and count toward volume; excessive mandatory solid is
rejected and a budget above available material is treated as an upper bound.

All 22 new tests pass, including independent Neumann eigenmode decay,
mass preservation, bounds and volume endpoints, interior nucleation, fixed
regions, all-fixed domains, load-case weighting, material-unit scaling,
unsupported scenarios and a feasible MBB run. Method conformance passes.
CLI MBB 24x8, 150 steps, gives linear compliance 230.917347 and volume 0.5;
this is an iteration-cap result, not convergence or an OC comparison. The
inspected `results/reaction-diffusion-validation/validation.png` shows density,
phi and volume history. A separate 60x20, 150-step study with diffusion lengths
0.5/1/3 mm yields 10/5/2 interior holes and compliances 193.793/190.863/214.989,
all at volume 0.5. This is benchmark evidence, not a universal monotonicity law.

Registry assertions and documentation now count 79 selectable plugins,
eight physics engines and 17 presets (104 implementations); 253 compositions
and two whole methods give 255 names. Ruff and whitespace checks pass.
All 1127 focused method, schema and GUI checks pass (`results/rd-focused.log`,
`results/rd-focused.xml`, 5 min 10 sec). The full native suite passes:
**2224 passed, one optional multigrid test skipped**, in 26 min 47 sec
(`results/rd-native-full.log`, `results/rd-full.xml`). Ruff and whitespace
checks pass. No baseline elements/goldens changed and no later method was
started during validation.

### Completed: Hamilton-Jacobi level set and circular-hole derivative

Added `methods/levelset_hamilton_jacobi.py`, an independent 2-D HJ/TD
implementation after Challis (2010), DOI 10.1007/s00158-009-0430-0. The public
article was read; no original MATLAB code was copied. Positive-inside phi
reverses the source convention. Godunov upwinding, CFL substeps, cross-shaped
sensitivity smoothing, solid-only topological forcing, EDT reinitialisation
and augmented-Lagrangian volume-fraction feedback follow its formulation.
Initial mean-cell-energy normalisation makes evolution invariant to load and
material units. Controller decay has a finite floor. Support/force cells are
protected in addition to user-fixed regions and counted in the budget.
Targets round down to binary cell counts; overspending cannot pass the joint
volume/compliance stopping criterion. This is not a port or an Amstutz geodesic
two-phase optimiser; generalised reinforcement algorithms remain candidates.

The plane-stress circular-hole derivative is
`(4 sigma:sigma - trace(sigma)^2)/E` per removed area. Its Q4 quadrature matrix
is checked independently for uniaxial, biaxial and shear stress at four Poisson
ratios, nonsquare elements and rigid motions. A separately loaded physical
plate with a central circular void gives compliance change/removed area
3.148 then 3.101 on refined meshes, approaching the infinite-plate value 3
with finite-domain and stair-step errors. This is not a SIMP density-gradient
finite difference. Unit-ball pi factors are retained in the forcing term.

All 28 method tests pass, including signed-distance offsets, both upwind
directions, source-only nucleation from flat solid, controller fraction
scaling/floor, combined load/material scaling, immutable regions, unsupported
scenarios and two actual same-mesh OC comparisons within the unchanged 10%
quality allowance. Method conformance and both CLI examples pass. MBB 24x8
settles feasibly at iteration 86, compliance 246.108358, volume 0.5; 60x20 at
iteration 110, compliance 191.667832, volume 0.5. The inspected
`results/hamilton-jacobi-validation/validation.png` shows the evaluated density,
signed-distance field and volume history. Other settings/problems may oscillate
or reach poor local minima; a cap is not convergence. Original MATLAB oracles
remain optional and were not run.

Documentation/registries now count 80 selectable plugins, eight physics
engines and 17 presets (105 implementations); 253 compositions plus three
whole methods give 256 names. Ruff and whitespace checks pass. All 1140 focused
method, schema and GUI checks pass in 5 min 12 sec (`results/hj-focused.log`,
`results/hj-focused.xml`). The full native suite passes: **2260 passed, one
optional multigrid test skipped**, in 29 min 46 sec (`results/hj-native-full.log`,
`results/hj-full.xml`). Ruff and whitespace checks pass. Original Q4/H8 sources
and golden baselines remain unchanged. No later method was started during
validation.

### Completed: phase-field regularised compliance

Added the `phase_field` objective response in `responses/phase_field.py`.
This is the permitted regularising-response route, composed with the existing
physics, material, representation and general gradient optimisers. The
functional is `C/C_full + gamma*mean(epsilon/2*|grad rho|^2 + rho^2*(1-rho)^2/epsilon)`.
Epsilon and gamma are physical mm. A conservative finite-volume Laplacian uses
real spacings and zero outer flux; the mean is the normalised physical integral
in 2-D/3-D. The penalty counts internal interfaces, not outside perimeter, and
does not promise a minimum feature size. An extra full-available-material FE
solve fixes the normalising compliance independently of the trial design.

The author manuscript of Takezawa et al. (2010), DOI 10.1016/j.jcp.2009.12.017,
was read. Its Section 2.3 distinguishes the density-based perimeter functional
of Bourdin & Chambolle (2003), DOI 10.1051/cocv:2002070, from its own shape-only
tilted-well Allen-Cahn method. This implementation follows the former energy
principle for two phases and fixed loads, with Toporia's existing optimisers.
It does not implement three-phase pressure loads, a dedicated Allen-Cahn/
Cahn-Hilliard integrator, fracture or phase-field frequency/mechanism objectives.
No original code is copied. The actual objective and its components are reported;
the model also records physical compliance, avoiding confusion between the two.

All 17 new tests pass. Independent face sums and complete discrete gradients
are checked in 2-D/3-D; planar interfaces have surface energy sqrt(2)/6 per unit
interface measure independently of width; chemical-potential residuals converge
quadratically. Coupled FE gradients pass on all five compatible native engines
(Q4, buckling, dynamic/static energy, mechanism, H8), maximum conformance error
8.6e-8. Tests also cover zero weight, fixed reference, proportional unit/case
scaling, metadata/parameter paths, a feasible MBB optimisation, 3-D composition
and invalid inputs. Compliance-only updaters do not offer this mixed-sign-gradient
objective. Thermal/nonlinear engines do not advertise its elastic feature.

The CLI example disables the density filter and resolves roughly three cells
across a planar interface (24x8, epsilon 2.5 mm, gamma 5 mm). At its 200-step cap:
J=2.082650298, normalised compliance 1.780957328, phase energy 0.301692970,
physical compliance 217.239466, volume 0.5. This is not a convergence or filtered-OC
comparison. `results/phase-field-validation/validation.png` was inspected and
shows the evaluated diffuse density, energy components and volume history.
Binary thresholding changes the design and its measured volume/compliance.

Registry assertions/documentation now count 81 selectable plugins, eight physics
engines and 17 presets (106 implementations). There are still 253 compositions
and three whole methods (256 names). Ruff and whitespace checks pass. All 1134
focused method, metadata and GUI checks pass in 5 min 15 sec
(`results/phase-focused.log`, `results/phase-focused.xml`). The full native suite
passes: **2280 passed, one optional multigrid test skipped**, in 25 min 41 sec
(`results/phase-native-full.log`, `results/phase-full.xml`). Ruff and whitespace
checks pass. Original Q4/H8 sources and golden baselines remain unchanged.
No later task was started during validation.

### Completed: explicit geometric minimum-length constraints

This addition follows the phase-field commit (`71abd18`). New response
`responses/minimum_length.py` uses Dunning's (2018) separate physical-density
cone filter and Zhou-type indicators, with a conservative nodal KS maximum
and fixed scaled 1-D tolerance. This is an independent variant, not either
paper's complete optimisation algorithm. Full physical-density gradients pass
conformance on all eight native engines (largest relative error 1.7e-10;
`results/length-conformance.log`). Independent 2-D/3-D filter, transpose,
finite-difference, complement, unit-scaling, KS-bound and feature-width tests
are in `tests/plugins/test_minimum_length.py`.

The geometric cone is constraint-only, truncated/renormalised at the boundary;
it does not alter the physics pipeline. Requested radius must span at least two
cells in every direction. The mesh can accept a bar one cell below the nominal
width; no exact manufacturing certificate is claimed. Tests and docs explicitly
distinguish that proxy from a true geometric width. Low indicator decay uses
the endpoint maximum of the paper's 1-D profile when its interior critical point
leaves the relevant interval.

Strict solid/void constraints at a uniform gray start stalled NLopt MMA, so those
trials are NOT accepted examples. Density+Heaviside projection and existing
tolerance/SIMP continuation with per-step pyMOTO MMA still left a solid residual
around +0.2 at a nominal 6 mm target on the 60x20 MBB mesh. A 700-step slower
GCMMA continuation finished with solid residual +0.953 and is also explicitly
rejected as infeasible (`results/length-gcmma-trial.log`). No success gate was
weakened to accept those runs.

The reproducible recipe is `python -m experiments.minimum_length`: a 24x16
cantilever, explicit resolved nearly binary straight-bar seed, 4 mm proxy target
for both phases, linear ersatz and no physical filter. NLopt MMA decreases
compliance from 115.115877 to 111.907874, volume 0.4999999991, fresh solid/void
residuals -2.22e-7/-3.23e-8. There are 244 NLopt evaluations and 246 FE solves
including independent initial/final checks. This modest local validation is not
a penalised SIMP benchmark or robust uniform-start topology creation. The
physical-density comparison figure was inspected. Fresh final evaluations are
required (ComposedMethod's ordinary responses can precede its latest update).

All 21 new geometric/optimisation tests pass in 6.94 sec; 55 focused response
and physics tests passed earlier in 3 min 18 sec. The full native run completed
in 28 min 13 sec: 2303 passed, one optional multigrid skip, one stale capability
assertion failed (`results/length-native-full.log`, `results/length-full.xml`).
The assertion expected multi-constraint OC to offer only stress; its generic
constraint contract also offers the new response. Only that expected tuple was
updated, with no solver/implementation changes. All six tests in its file pass
on rerun in 12.62 sec (`results/length-oc-final.log`, `length-oc-final.xml`). Thus
all 2304 current tests have passing coverage; the single monolithic log retains
the original assertion failure rather than being presented as a clean run.
Ruff and whitespace checks pass. GUI reachability, physics conformance and
original golden checks all pass. Original Q4/H8 sources and goldens are unchanged.

The catalogue now has 82 selectable plugins, eight physics engines and 17 presets
(107 implementations), including 13 responses. There are 253 compositions and
three whole methods (256 names). No later task was started during validation.

### Remaining sequence

1. Machining accessibility and projection-based self-support.
2. Multiresolution design and analysis meshes.
3. Neural reparameterisation (TOuNN), subject to dependency support on this Python/Windows setup.

Heat conduction, thermal/dynamic pyMOTO models, eigenfrequency, harmonic response,
local stress with augmented Lagrangian, and nonlinear elasticity are already
present and covered by the stabilisation milestone.

Original MATLAB/Octave reference runs remain optional, as agreed in the previous
handoff. Ask the owner before installing or changing runtimes to obtain them.
Source papers, licences, gradients, physical benchmarks, GUI reachability, CLI
examples and documentation must be checked for every addition. Never regenerate
golden baselines to accommodate a change.
