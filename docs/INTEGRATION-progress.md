# Integration status

Work stays in `toporia-integration` on `integration/physics`. The GUI and launcher
checkouts are separate. The owner reviews and merges; no push or merge is implied.
This is a concise handoff. Historical implementation and validation summaries remain in Git.

## Scope

The agreed round covers the small and medium tasks on page 7 of the original
`Toporia-library.pdf`. Existing physics is validated rather than added twice.
Large framework bridges, datasets, SINH and Hashin-Shtrikman laws are outside
this round. `Toporia-library-with-links.pdf` is the updated linked snapshot.

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

Heat conduction, thermal/dynamic pyMOTO models, eigenfrequency, harmonic response,
local-stress augmented Lagrangian and nonlinear elasticity are already present.
The catalogue has 82 selectable plugins, eight physics engines and 17 presets:
107 implementations. Eleven models and 23 updaters form 253 compositions;
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
- Original MATLAB/Octave oracle runs remain optional. Ask before installing or
  changing runtimes. Original Q4/H8 sources and golden baselines are unchanged.

## Current verification and cleanup

Compare Methods has a parametrised GUI-to-engine test for every registered preset.
It checks preserved scenarios, valid defaults, actual short runs, grids and CSVs.
These use coarse meshes and three iterations to test wiring, not convergence.
An additional bounded audit passed all 321 compatible preset/updater combinations
on the presets' own physics; 70 incompatible combinations were excluded.
Thermal comparisons measure heat rather than zero mechanical work; vibration
reports fundamental angular frequency. Preset-recommended methods remain selected.

The final full suite passes: **2332 passed, one optional multigrid test skipped**
in 25 min 9 sec. Ruff and whitespace checks pass; all local Markdown links resolve.
Generated runs, downloaded papers, scratch scripts/images and caches are removed
after validation. The implementation, regression tests, reusable research recipes
and library PDFs remain. The one-off PDF builder is removed as requested.

## Remaining sequence

1. Machining accessibility: obtain a readable full text of Langelaar (2019),
   DOI `10.1016/j.cma.2019.03.037`; the institutional download failed.
2. Projection-based self-support (Gaynor and Guest).
3. Multiresolution design and analysis meshes.
4. Neural reparameterisation (TOuNN), subject to this Python/Windows environment.

No later research integration was started during the GUI and comparison fixes.
