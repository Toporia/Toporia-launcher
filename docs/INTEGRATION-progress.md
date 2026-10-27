# Integration status

Work stays in `toporia-integration` on `integration/physics`. The GUI and launcher
checkouts are separate. The owner reviews and merges; no push or merge is implied.
This is a concise handoff. Historical implementation and validation summaries remain in Git.

## Scope

The agreed round covers the small and medium tasks on page 7 of the original
`Toporia-library.pdf`. Existing physics is validated rather than added twice.
This round covers all remaining small/medium additions, including SINH and
Hashin-Shtrikman laws. Large framework bridges and datasets remain outside it.
`Toporia-library-with-links.pdf` preserves the linked catalogue and opens with
a current-round update containing additions, validation and limitations.

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

Heat conduction, thermal/dynamic pyMOTO models, eigenfrequency, harmonic response,
local-stress augmented Lagrangian and nonlinear elasticity are already present.
The catalogue has 88 selectable plugins, nine physics engines and 18 presets:
115 implementations. Twelve models and 23 updaters form 276 compositions;
three whole methods bring the method-name total to 279.

## Important limits

- MMV is the restricted 2-D variant; geometry projection uses fixed-radius capsules.
- Phase field is an energy response, not a dedicated Allen-Cahn/Cahn-Hilliard solver.
- The HJ/TD method is not a standalone Amstutz geodesic optimiser.
- Minimum-length constraints are calibrated geometric proxies, not exact size
  certificates. Strict two-phase constraints can stall at uniform gray starts.
  The feasible-seed recipe in `experiments/minimum_length.py` is deliberately local.
- The annealing experiment misses the unchanged 10%-of-OC gate and is not registered.
- Point springs require `q4_mechanism`. Updater and objective compatibility still
  applies. MMA and CONLIN produce force inversion; other optimisers may find
  disconnected zero-output stationary designs.
- Original MATLAB/Octave oracle runs depend on an available runtime. Ask before
  installing or changing runtimes. Original Q4/H8 sources and golden baselines
  are unchanged.

## Current verification and cleanup

Compare Methods has a parametrised GUI-to-engine test for every registered preset.
It checks preserved scenarios, valid defaults, actual short runs, grids and CSVs.
These use coarse meshes and three iterations to test wiring, not convergence.
An additional bounded audit passed all 321 compatible preset/updater combinations
on the presets' own physics; 70 incompatible combinations were excluded.
Thermal comparisons measure heat rather than zero mechanical work; vibration
reports fundamental angular frequency. Preset-recommended methods remain selected.

Final verification on 27 October: **2655 passed, one optional multigrid test skipped**
in 36 min 58 sec. Four added external-reference tests pass separately: the current
collection contains 2660 cases, so all 2659 runnable cases pass. The full run
reports 95 warnings from third-party pyMOTO/SciPy paths. Ruff and whitespace
checks pass; all 513 local Markdown file links resolve.
Generated runs, downloaded papers, scratch scripts/images and caches are removed
after validation. The implementation, regression tests, reusable research recipes
and library PDFs remain. The one-off PDF builder is removed as requested.

## Current round — 26 October 2026

Machining accessibility is implemented as an independent Høghøj–Träff Cartesian
advection–diffusion filter. The full derivation is readable at arXiv:2102.12999;
the institutional copy of Langelaar (2019) remained inaccessible. This is not a
claim to reproduce Langelaar's finite-tool formulation. It supports 2-D/3-D
axis directions and passive-solid shadows, with complete transpose solves.
Forced voids and non-element representations are refused. The chain must end
with machining. Element-density starts meet the physical budget; convergence
also observes physical-density movement to avoid premature small-source stops.

Twenty-five focused tests and the full regression suite pass. The 80-iteration MMA recipes improve compliance
and meet volume budgets, with zero inaccessible void cells in an independent
thresholded ray check. They are coarse bounded runs, not convergence claims or
finite-tool certificates; see `experiments/machining.py`. The linked PDF includes
the new method and the earlier mechanism/comparison fixes; all 281 existing
links and three outline entries are preserved, with three new links added.

Gaynor–Guest self-support is implemented as a cell-centred 2-D wedge projection
and local exponential projection, with a complete reverse sweep. Only Cartesian
build directions, element densities and unpinned boxes are supported. The support
threshold depends on the grid/angle; no exact size/angle or printing certificate
is claimed. Both sharpnesses support continuation. Small move limits down to
0.00001 now survive schema and GUI round trips; the 0.2 default is unchanged.

The focused manufacturing/schema/variant group passes 434 tests; all 53 selected
GUI form, reachability and small-move tests pass. Twenty-one self-support tests
are included; 16 unchanged golden cases also pass. Ruff passes and all 491 local
Markdown links resolve. The linked PDF adds a second update page (15 pages,
286 links), preserving its existing catalogue and navigation. Fine-grid MMA/GCMMA runs improve compliance and meet smooth-volume
budgets; they remain unconverged and retain gray material. Binary thresholding
exceeds budgets and can leave one-layer support discrepancies. These results are
explicitly recorded in `experiments/README.md`, not presented as printable designs.

Multiresolution now supports a fine Cartesian density grid with a nested coarse
Q4 displacement grid. Loads transfer by virtual work and fine supports are imposed
as interpolation constraints. Factor 1 retains the original Q4 path bit for bit;
larger factors require divisible mesh counts. This aligned 2-D variant uses exact
fine-cell quadrature, not the original MTOP centroid rule or an adaptive/three-mesh
implementation. Complete compliance gradients pass independent finite differences.
Independent subcell quadrature, off-grid supports and disconnected-cut tests cover
the approximation's important behaviour. Compare Methods still uses fine Q4 as
its referee. Coarse compliance can substantially overstate disconnected designs.

The broad multiresolution/composition/schema/golden group passed 987 tests;
102 selected GUI tests passed. Bounded 100-step MBB/cantilever benchmarks roughly
halve solve time in single-run measurements, with fine-compliance underestimates
of 2.21% / 1.87%. They are not converged; one OC volume is 0.500019 against 0.5.
Results and limits are recorded in `experiments/README.md` and the linked PDF.

The `neural` representation is an independent smooth TOuNN-style coordinate MLP,
with tanh hidden layers, sigmoid density output and explicit NumPy backpropagation.
It supports 2-D/3-D through existing models, filters and general-vector updaters.
It is not a port of the reference's GPL PyTorch code: batch normalisation,
LeakyReLU, density offset, AMSGrad and built-in manufacturing rules are absent.
No new runtime is installed. The existing Adam augmented Lagrangian is reused.
Sixteen focused tests cover all parameter derivatives, physical/filter gradients,
deterministic starts, mesh-independent parameter count and updater preflight.
The combined representation group passes 40 tests, and 53 selected GUI form and
reachability cases pass. Bounded 600-step Adam/MMA runs improve compliance and
meet smooth-volume budgets, but retain 38-83% gray cells; no convergence or
crispness claim is made. The recipe and measured limits are in experiments/PDF.
The broader schema/composition/unchanged-golden group passes 957 tests. Ruff,
whitespace and all 503 local Markdown file links pass. The updated PDF has 17
pages and 290 links, preserving its three original internal links and outline entries.

## SINH — 27 October 2026

Basic SINH uses linear stiffness and Bruns' nonlinear effective volume (equations
22-23). The implemented shared-density variant is Table 2 case 5 with a density
filter, case 4 without filtering. The case-6 resource-only filter and hybrid
stiffness penalties remain outside it. Identity volume hooks on other laws keep
their numerical behaviour. Effective cost now reaches the assembled model's
evaluation, cheap updater volume checks, volume objective and complete adjoints.
Element-density starts are calibrated to its budget. History keeps the displayed
geometric volume, with effective cost reported separately on the current design.
Limit checks and study feasibility use effective cost; studies add a separate
effective-volume column and keep the common SIMP p=3 referee.

Twenty-four focused SINH tests include 2-D/3-D FE/filter/representation derivatives,
five updater paths, nominal variants, continuation, volume objectives, pinned
material and feasibility reporting. The 53-case focused/interpolation/golden group
passes. Bounded 300-step MBB/cantilever runs improve compliance and fit effective
budgets; they retain 33.75% / 27.22% gray material and are not converged. Full
measurements and scope are in the experiment README and linked PDF.
The manufacturing/variants/study/SINH group passes 72 tests, with 53 selected
GUI cases passing. Ruff, whitespace and 506 local Markdown file links pass.
The PDF has 18 pages and 292 links, preserving the original navigation.

## Hashin-Shtrikman — 27 October 2026

The law binds the scenario's actual nu and dimension through an optional
interpolation setup hook. Ordinary laws keep a no-op setup. A shared compatibility
hook refuses elastic HS laws on thermal models before studies/runs start.
The implemented scalar law follows the stricter of the HS bulk/shear upper
limits along the solver's fixed-nu ray, including finite Emin in both phases.
It supports plane stress and 3-D solid elasticity without changing the original
Q4/H8 numerical sources. The exact slope feeds existing response adjoints.

Scope is explicitly an upper envelope: this is not the paper's density-varying
nu (eq.17), lower-bound enforcement, arbitrary phase Poisson ratios or proof of
microstructure realisability. The 2-D nu=1/3, Emin=0 special case is recovered.
Seventy-seven focused tests cover independent reciprocal HS formulas, six nu
values, five contrasts, both dimensions, physical adjoints and thermal preflight.
The focused/interpolation/unchanged-golden group passes 106 tests. Bounded 300-step
MBB/cantilever runs improve compliance and meet geometric budgets, retaining
34.83% / 26.72% gray material. They are not converged; full measurements and limits
are in the experiment README and linked PDF.
The combined HS/SINH/schema/variants/study group passes 504 tests and 53 selected
GUI form/reachability cases pass. Ruff, whitespace and all 510 local Markdown
file links pass. The PDF has 19 pages and 294 links with original navigation intact.

## Original MATLAB references — 27 October 2026

MATLAB R2026a Update 5 is installed and licensed; the direct batch route works
without a Python Engine install. Unmodified top88 and top3d were downloaded
from author sources and hashed. Three cases match Toporia's stopping iteration
and first/last printed objectives to four-decimal precision. Both top88 mean
densities also agree within 1e-10. The top3d reference recipe explicitly uses
the original equal nodal depth forces; production line-load quadrature is unchanged.
Native observations and hashes are stored separately from unchanged golden
baselines in `tests/references/matlab.json`. A reusable optional driver verifies
supplied source hashes, uses isolated temporary files and changes no MATLAB path.

Original TOPRBF(40,20,0.5) completes in 88 steps with C=594277.942780 and volume
0.499728; the 24x8 attempt produced non-finite fields and is rejected. The native
RBF result is a standalone reference, not a strict oracle for Toporia's mean-
normalised and guarded variant. An inaccurate port/authorship description was
corrected; the existing RBF algorithm and baselines are unchanged.

Other originals remain unresolved: fsparse is absent and no C compiler is
selected; MMC needs absent mmasub/subsolv; original TOBS101 errors on its removed
intlinprog CutGeneration option; Challis' source returns a challenge page and
the reaction-diffusion source host is unavailable. The owner was asked for any
existing local original/helper files. No compiler, toolbox or runtime is installed
or reconfigured. These gaps do not invalidate the three matching reference cases.
All four external-fixture tests pass, including source-hash refusal before MATLAB
launch. The optional native rerun driver also reproduces all three original cases.
Ruff, whitespace and 513 local Markdown file links pass. The PDF has 20 pages
and 296 links; its original internal links, outlines and catalogue are preserved.
Downloaded sources, traces, intermediate fields and PDF builders are removed.

## Remaining sequence

1. Complete a bounded audit of remaining original MATLAB reference cases. Do not
   install dependencies, configure a compiler or change MATLAB without asking.
2. Stronger bounded practical validation of self-support, neural and minimum-length recipes.
3. Correct console objective reporting and malformed structured CLI configuration errors.
4. Verify L-bracket and robust-formulation provenance, then reconcile catalogue/TODO status.

Work stays sequential: finish verification, documentation and one commit per
addition before starting the next. No generated runs or scratch papers are retained.

## Fixed projection — 27 October 2026

`MBB Beam (Fixed Projection)` composes existing density, Heaviside and MMA parts.
Beta and beta_max stay 16; initial asymptotes follow Høghøj & Träff §3.1 eq.(11),
with their conservative growth/shrink settings. This is an independent recipe,
not a verified port of the subscription-only Guest et al. (2011) paper. The old
claim that eliminating continuation necessarily needs a new filter is corrected.
The MMA form retains enough decimal places to preserve the initial spacing.
Two 600-step runs meet physical volume limits and retain 1.00% / 0.89% gray cells,
but do not meet MMA's stricter change tolerance. Measurements and limits are in
the experiment README. Three focused tests, five preset/reachability GUI cases and
three GUI-precision/unchanged-MMA-golden cases pass. Ruff and whitespace checks
pass. The PDF has 21 pages and 299 annotations with original navigation preserved.

## Remaining original-reference audit — 27 October 2026

Added `experiments.original_references --audit-matlab`, a read-only batch check
of runtime, licence, helper locations and selected compiler. Native execution
confirms R2026a Update 5 and Optimization Toolbox, absent fsparse/MMA/level-set
helpers and no selected C compiler. No installation or MATLAB settings changed.
Challis' main publisher source now downloads (hash recorded), but its bwdist
helper still returns HTML; bwdist/padarray are absent from the installed toolbox.
The primary top99neo/top3D125 page confirms fsparse is required; its author repo
has no binary releases. RD's author host remains unavailable. Original TOBS101
still needs a separately labelled compatibility adaptation for removed options.
The experiment README has the per-original requirements. Numerical comparisons
remain blocked; compiler/helper installation requires the owner's pending decision.
The previously passing three reference cases and golden baselines are unchanged.

## Stronger self-support validation — 27 October 2026

Same-setting GCMMA runs extended from 500 to 1000 steps improve MBB/cantilever
compliance to 391.36346 / 284.11337 and meet smooth budgets. They remain
unconverged (changes 0.01428 / 0.01231) with 20.08% / 16.56% gray cells.
The experiment now re-solves binary fields using both cutoff 0.5 and a strict
cell-count cutoff that respects the volume budget. The latter gives exactly
0.5 / 0.4 volume, C=319.60022 / 235.27987 and zero unsupported cells under the
independent one-layer 45-degree stencil on both fields. This is not a printing
certificate or generic support repair. All 21 core geometric/adjoint tests and
Ruff pass; core filter mathematics and golden baselines are unchanged.
The owner has now approved an isolated compiler/helper setup under
`C:\Users\johan\AppData\Local\ToporiaValidation`, with no global PATH or MATLAB
startup/default-compiler changes. Broader changes still require approval.
Return to the original-reference checks after this validation commit, then
continue neural/minimum-length validation and the remaining small fixes.

## Isolated reference tools and native MMA — 27 October 2026

Approved portable GCC 14.2 and author fsparse are installed only under
`C:\Users\johan\AppData\Local\ToporiaValidation`. Compiler archive checksum,
author source revision/hash and compiled MEX hash are recorded in the external
fixture. Build setup asserted an isolated MATLAB_PREFDIR before selecting the
compiler; MW_MINGW64_LOC was process-local. No global PATH, saved MATLAB path
or normal default compiler changed. Four sparse-assembly checks pass.
An identified GPL Svanberg MMA distribution copy with embedded subsolv was
run unchanged on a six-variable convex reciprocal problem. mmapy's first/final
designs, fresh objective, multiplier and volume agree within 1e-10; its objective
also agrees with the analytic optimum to 2e-9 relative tolerance. The source
copyright/COPYING stay in the external tool folder; no third-party code is bundled.
`experiments.original_references --mma` and a regression test reproduce Python.

The licensed Image Processing Toolbox is absent, blocking imfilter and the
Challis helpers. The owner approved a toolbox-only R2026aU5 addition, then chose
to install it personally after Windows refused elevation/write access. The
agent's installer exited unsuccessfully; it did not add the toolbox or upgrade
MATLAB. Await owner confirmation before dependent native checks. The existing
MATLAB source and original golden baselines remain unchanged.

## Stronger neural validation and convergence fix — 27 October 2026

Added optional fixed projection, seed selection, final-stage weight moves,
independent physical-change reporting, volume-limited thresholded solves and
finer-grid evaluation of learned weights to the reusable neural recipe.
Two seeds, two presets and 1000-step caps do not produce useful binary designs:
89–100% gray cells remain after settling. Coarse budgets are met within 2e-7,
but finer cantilever volumes exceed the target by up to 8.5e-5. Binary cutoffs
produce very poor compliance; the README retains the full failure evidence.

Unsettled fixed projection exposed physical changes up to 0.32 while weights
move only 0.005. The new opt-in representation trait makes neural composed
methods monitor physical density as well as weights for convergence; existing
element/other-representation behavior is unchanged. A regression reproduces
the mismatch and checks the larger change is reported. All 18 neural tests pass,
including a sharp-projection physical adjoint. This is a stopping correction,
not a claim that the smooth independent network reproduces original TOuNN.
The composition/variants/unchanged-golden/self-support group passes 611 cases
(68 existing third-party warnings); Ruff and whitespace checks pass.

## Stronger minimum-length validation — 27 October 2026

The reusable recipe now prints only unless --out is explicit. It compares the
existing feasible straight-bar seed and uniform gray start, plus binary and
2x-grid physical-field re-evaluations at the unchanged 4 mm proxy target.
The seeded result reproduces C=111.907874 and coarse feasibility. Its binary
field is feasible on both grids (C=116.34435 / 117.60605), but the smooth field
fails on refinement with residuals +13.86719 / +12.80328. The mesh-dependent
nodal tolerance and remaining gray densities prevent transferring feasibility.
The uniform start stops after two NLopt evaluations with FTOL_REACHED while
both residuals remain +13.87811; the independent feasible flag is false and
the CLI exits nonzero. Thresholding uniform gray to empty also shows that
geometric proxies alone do not ensure load-bearing capability. All 21 tests,
Ruff and whitespace checks pass. No response formula or tolerance was weakened.

## Console objective reporting — 27 October 2026

The iteration console now prints the actual reported objective, matching the
stored response/history, instead of labelling a delta from the first value as
obj. Positive compliance and negative frequency-objective histories are checked
end to end, including the first printed value. Recording, objective mathematics
and optimization updates are unchanged.
All 12 analysis-mode tests pass, including both console cases; Ruff passes.
