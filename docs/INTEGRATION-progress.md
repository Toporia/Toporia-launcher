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

Heat conduction, thermal/dynamic pyMOTO models, eigenfrequency, harmonic response,
local-stress augmented Lagrangian and nonlinear elasticity are already present.
The catalogue has 84 selectable plugins, eight physics engines and 17 presets:
109 implementations. Eleven models and 23 updaters form 253 compositions;
three whole methods bring the method-name total to 256.

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

After machining, the full suite passed: **2363 passed, one optional multigrid test skipped**
in 27 min 57 sec. Ruff and whitespace checks pass; all 486 local Markdown links resolve.
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

## Remaining sequence

1. Multiresolution design and analysis meshes.
2. Neural reparameterisation (TOuNN), subject to this Python/Windows environment.
3. SINH and Hashin–Shtrikman material laws.
4. Original MATLAB/Octave reference runs if a suitable runtime is available;
   ask before installing or changing runtimes.

Work stays sequential: finish verification, documentation and one commit per
addition before starting the next. No generated runs or scratch papers are retained.
