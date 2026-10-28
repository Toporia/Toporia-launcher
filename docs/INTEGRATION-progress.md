# Integration status

Work stays in `toporia-integration` on `integration/physics`. The GUI and launcher
checkouts are separate. The owner reviews and merges; no push or merge is implied.
Current handoff: 27 October 2026. Detailed historical measurements remain in Git
and the [experiment recipes](../experiments/README.md).

## Scope

The agreed round covers the small and medium tasks on page 7 of the original
`Toporia-library.pdf`. Existing physics is validated rather than added twice.
This round covers all remaining small/medium additions, including SINH and
Hashin-Shtrikman laws. Large framework bridges and datasets remain outside it.
`Toporia-library-with-links.pdf` preserves the linked catalogue and opens with
a current-round update containing additions, validation and limitations.

The [research origins audit](research-origins/README.md) records the cited
literature's geography and publication history as of 27 October 2026. It includes
an interactive map and timeline, 82 reference records in CSV/JSON, connections to
the implemented features, and citation caveats. The map locates 54 references
(53 verified affiliation assignments and one labelled historical inference);
28 references have unresolved geography. This documentation does not add plugins
or change implementation counts.

## Completed integrations

| Commit | Addition / scope |
| :-- | :-- |
| `2dc42a1` | Stabilised existing physics and compatible model/updater compositions. |
| `b9f7a7f` | Q4 linearised buckling, full adjoint and column benchmark. |
| `ce9f4e2` | Conservative anisotropic Helmholtz filter, 2-D/3-D. |
| `6a10f2b` | Restricted 2-D superelliptical moving morphable voids. |
| `00ffa9b` | Floating projection with internal beta continuation. |
| `8116acf` | Standard annealing evaluated outside the registry; performance gate failed. |
| `4496e90` | Port springs, signed displacement objective and Force Inverter preset. |
| `55c019e` | Independent 2-D/3-D capsule geometry projection. |
| `c76509f` | Cell-centred reaction-diffusion level set with elastic topological sensitivity. |
| `a27b13b` | Hamilton-Jacobi evolution and circular-hole topological sensitivity. |
| `71abd18` | Phase-field regularised-compliance objective, 2-D/3-D. |
| `9abc824` | Solid/void geometric minimum-length constraints and complete adjoint. |
| `9c901b3` | GUI preserves small loads; Force Inverter's 0.001 N input no longer becomes zero. |
| `81c9c37` | Compatible method-study selections, spring-aware measurement and mechanism metrics. |
| `4decae8` | Cartesian PDE machining, full adjoints and physical-volume starts/convergence. |
| `314b2b6` | Cell-centred Gaynor-Guest self-support, full reverse sweep and small-move controls. |
| `d74d056` | Nested 2-D Q4 multiresolution, exact subcell integration and independent fine referee. |
| `5700fc5` | NumPy smooth TOuNN-style coordinate field with explicit 2-D/3-D backpropagation. |
| `819a111` | Basic shared-density SINH, effective-volume budget/adjoints and separate reporting. |
| `124b902` | Scenario-bound fixed-nu Hashin-Shtrikman upper envelope, 2-D/3-D and thermal preflight. |
| `eef0328` | Three strict original MATLAB reference cases, qualified RBF observation and source/dependency audit. |
| `7c146ea` | Fixed-beta projection/MMA preset and GUI asymptote precision. |
| `d578545` | Read-only MATLAB prerequisite audit. |
| `779aee4` | Longer self-support checks and budget-limited binary diagnostics. |
| `712c564` | Isolated fsparse/MMA setup and native MMA reference. |
| `8864204` | Neural physical-density convergence monitoring and bounded validation. |
| `073f6f3` | Minimum-length initialisation/refinement audit; print-only default. |
| `c0fe5ca` | Actual signed objective in console output. |
| `51cff02` | Clear structured CLI argument errors before physics/output creation. |
| `6e92407` | Newly unblocked native originals and strict additional FE comparisons. |
| `dbdb55d` | L-bracket/robust provenance and explicit guarantee limits. |

Heat conduction, thermal/dynamic pyMOTO models, eigenfrequency, harmonic response,
local-stress augmented Lagrangian and nonlinear elasticity are already present.
The catalogue has 88 selectable plugins, nine physics engines and 18 presets:
115 implementations. Twelve models and 23 updaters form 276 compositions;
three whole methods bring the method-name total to 279.

## Validation and practical limits

- **Fixed projection:** beta=16 with tightened MMA asymptotes. MBB/cantilever
  600-step runs meet physical budgets, with 1.00%/0.89% gray cells; neither meets
  the stricter 1e-4 MMA change tolerance. An independent recipe, not all Guest variants.
- **Machining:** independent Cartesian advection-diffusion filter, 2-D/3-D and
  passive-solid shadows. Forced voids/non-element representations are refused.
  Bounded 80-step runs meet budgets and pass a thresholded ideal-ray check;
  no finite cutter/holder or convergence certificate.
- **Self-support:** independent 2-D cell-centred wedge/local projection. Longer
  1000-step GCMMA runs remain unconverged with 20.08%/16.56% gray material.
  Threshold 0.5 exceeds both budgets and leaves one unsupported cell each.
  Budget-limited thresholds give zero unsupported cells in the discrete check;
  this is not a printing certificate or a default optimizer change.
- **Neural field:** opt-in physical-density convergence prevents premature small-
  weight stopping. Fixed-beta MMA recipes tested at two seeds remain 89–100%
  gray after small-move settling; thresholded FE compliance is poor. Fine-mesh
  evaluations test the same weights without retraining. This is a documented
  failed binary-design recipe, not a recommended production default.
- **Minimum length:** calibrated geometric proxies with a full adjoint, not exact
  size certificates. The feasible start reaches a locally feasible coarse design;
  its remaining gray densities violate the proxy after 2x mesh refinement.
  A uniform gray start stalls infeasible after two evaluations. The experiment
  prints by default and refuses to call that start successful.
- **Multiresolution:** aligned nested 2-D Q4 with exact fine-cell quadrature;
  coarse displacement spaces can overstate disconnected designs. Fine Q4 remains
  the independent study referee. No 3-D/adaptive enrichment or stiffness certificate.
- **Material laws:** basic shared-density SINH and fixed-nu Hashin-Shtrikman
  upper envelope only; no hybrid SINH/separate resource fields or variable-nu HS.
- MMV is restricted 2-D; capsule geometry projection has fixed radii. Phase field
  is an energy response, and HJ/TD is not a standalone Amstutz geodesic optimizer.
  Annealing misses the unchanged performance gate and remains unregistered.
- Point springs require `q4_mechanism` plus a compatible updater/response.
  MMA/CONLIN invert force; other optimizers can settle at disconnected zero output.
- L-bracket geometry/load/budget are Toporia choices. The robust preset uses a
  smooth maximum and intermediate volume, unlike Wang's dilated-volume formulation;
  it does not certify manufacturing tolerance. Source links are in the preset docs.

## Original MATLAB references

The owner installed Image Processing Toolbox in R2026a Update 5. No MATLAB upgrade
was needed. The approved portable compiler, fsparse MEX, original sources and MMA
helper remain outside the repo under `%LOCALAPPDATA%/ToporiaValidation`. They use
process-local settings and isolated preferences; normal PATH, MATLAB startup,
saved path and default compiler selection were not changed. Ask before any further
installation or MATLAB change.

- Strict original trajectories: top88 sensitivity/density filters and top3d.
- Strict native MMA convex-problem reference, separate from Toporia's one-budget MMA.
- Additional strict FE checks: Challis initial/final binary field and top3D125
  initial sine-front-face load. These do not assert optimizer-trajectory equality.
- Unchanged top99neo/top3D125 runs complete as bounded observations. Sharp neo
  oscillates; top3D125 ends at reported volume 0.309 against 0.3. TOPRBF remains a
  qualified observation with different normalization conventions.
- TOBS unchanged source uses removed MATLAB options. A separately hashed temporary
  compatibility copy hits its safety cap with poor compliance and is rejected.
- MMC188 and reaction-diffusion lack a retrievable, byte-identifiable runnable
  author source. Paper transcriptions would not be unchanged original oracles.

Reference commands, source hashes, captured fields and scope live in
[experiments/README.md](../experiments/README.md) and `tests/references/matlab.json`.
Generic whole-method MATLAB Engine wrappers remain a separate framework project.

## Verification and cleanup

Compare Methods has preset-by-preset GUI-to-engine coverage plus a bounded audit
of 321 compatible preset/updater combinations; 70 incompatible pairs are excluded.
The new fixed-projection preset has separate reachability/round-trip/study checks.
Thermal and vibration comparisons use their physical metrics.

Before this final follow-up round, the full suite passed 2655 tests with one optional
multigrid skip in 36m58s; four then-added reference tests passed separately.
That is a dated baseline, not a claim to have rerun the entire current suite.
After the neural core change, 611 composition/variant/golden/manufacturing tests
passed. Focused groups also passed: neural 18, minimum-length 21, CLI 26,
analysis modes 12, original references 7, plus fixed-preset and GUI precision checks.
Third-party pyMOTO/SciPy warnings remain. Final follow-up: 111 focused tests and 56 GUI preset/round-trip/
reachability checks pass. Ruff passes across code, tests and experiments; all
526 local Markdown file links resolve. The 16-page updated PDF retains the
13 catalogue content streams, three internal links and three outlines. Original Q4/H8 sources and goldens stay unchanged.

Generated run outputs, downloaded papers, scratch scripts/images and our caches
are removed after validation. Reusable experiments, tests, implementation and
library PDFs remain. Concurrent research-origins documentation is preserved and
excluded from this work's commits.

## Remaining work

The agreed small/medium implementation and bounded-validation round is complete,
within the explicit scopes above. There is no unfinished active task in this round.
Original-source gaps, rejected recipes and unreproduced paper variants are limitations,
not silently completed full ports. Further tuning, complete external reproductions,
whole-method bridges and large framework/dataset work require a new agreed scope.
The owner reviews and merges the independent branches; nothing is pushed or merged.
