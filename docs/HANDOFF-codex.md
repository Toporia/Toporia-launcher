# Handoff: what is still to do (for Codex)

Written 2026-10-25. This file is for an agent that continues the work on Toporia. It lists what
is done, what is half done (**buckling**), and what is still to add from the "small" and
"medium" lists. It also gives the rules a new part must follow.

## 1. Where things are

| Branch | State |
| :-- | :-- |
| `main` | Release v0.2 (tag `v0.2`). Do not commit to it, and do not merge into it: the owner reviews and merges. |
| `integration/all` | v0.2 + all integrated parts + the GUI branch. Fully tested (999 passed). |
| `integration/physics` | `integration/all` + heat conduction, vibration (eigenfrequency and harmonic), local stress with augmented Lagrangian, and geometrically non-linear elasticity. **Continue from here.** |
| `wip/buckling` | Unfinished linearised buckling, written but **never run**. Based on an older commit. See section 3. |

The overview of every part and its source is `toporia/plugins/LIBRARY.md` (also used to make
the PDF). The working plan is `toporia/plugins/TODO.md`.

## 2. Rules every new part follows (tests enforce most of them)

1. **One file per part in the right folder, registered automatically.** A class in
   `toporia/plugins/<kind>/` with a non-empty `name` is registered. Read `docs/writing-plugins.md`.
2. **New physics is a new engine.** Don't change `plugins/physics/q4_plane_stress.py` or
   `h8_solid.py`. Subclass or import them instead (see `q4_dynamic.py`, `q4_nonlinear.py`,
   `q4_heat.py`). The golden tests in `tests/golden/` must stay bit-identical. Never regenerate
   their baselines.
3. **Features:** an engine declares `provides = (...)` feature names, and a response declares
   `requires = (...)`. New features get their own section in `toporia/framework/parts/physics.py`.
   Existing sections: ELASTIC_ENERGY, STRESS, THERMAL_ENERGY, NONLINEAR (END_COMPLIANCE),
   MODES, HARMONIC.
4. **`reference` on every plugin class** (tested by `tests/apps/test_gui.py`). It names the paper and
   ends with ` Papers: https://doi.org/...`, which the GUI's "?" popup turns into links. Check
   every DOI in Crossref (`https://api.crossref.org/works?query.bibliographic=...`). Several DOIs
   written from memory were wrong. Presets need `ABOUT` and `REFERENCE` module constants.
5. **Reachable in the GUI:**
   `tests/apps/test_gui.py::test_every_registered_part_and_preset_can_be_picked_in_the_gui`
   must pass. Objectives and constraints only appear for a model that can compute them, so a
   new physics needs a preset that uses it.
6. **Conformance:** `python -m toporia check <kind>:<name>` must pass. It checks the interface,
   the gradients against finite differences and, for updaters, an MBB benchmark within 10 %
   of OC.
7. **Docs:**
   - In the folder's README: a ✅ row, plus a section saying what the part does, with the paper
     link and how to use it in the GUI and on the command line. Run the CLI example yourself.
   - In `toporia/plugins/LIBRARY.md`: add the row, and remove the item from "To add next".
   - Then update the count tables in `toporia/plugins/README.md` and the top-level `README.md`.
8. **Python 3.14 on Windows:** `/c/Users/johan/AppData/Local/Python/pythoncore-3.14-64/python.exe`.
   It is not on PATH in bash; use `PYTHONPATH=.` for `-m toporia`. The full suite takes 10–20 min.
9. **Commit messages** end with the co-author line the repository already uses. Don't push to
   `main`. Don't commit scratch files (`*.npy`, `results/`).

## 3. Buckling: exactly where it stands

**What it is:** linearised buckling on 2-D Q4, after Ferrari, Sigmund & Guest, "Topology
optimization with linearized buckling criteria in 250 lines of Matlab", *SMO* 63 (2021)
3045–3066, https://doi.org/10.1007/s00158-021-02854-x.

**State:** an agent wrote all of it, then had to stop before running anything. It is saved
unreviewed in one commit, `e081d88` on branch `wip/buckling`. **Nothing in it has been run:
no test, no `toporia check`, no import.**

Files in that commit:

| File | What it should be |
| :-- | :-- |
| `toporia/plugins/physics/q4_buckling.py` (212 lines) | Subclass of `Q4PlaneStress`. Adds the element geometric (stress) stiffness K_σ(u) from the linear prebuckling stress, the generalised eigenproblem (K + λ K_σ) φ = 0 for the lowest positive load factors (scipy `eigsh`, shift-invert, supports applied), and the load-factor sensitivities including the adjoint term through u. K_σ uses its own interpolation exponent, to avoid spurious modes in void. |
| `toporia/plugins/models/q4_buckling.py` | The model, "2-D Q4 with buckling (Toporia)". |
| `toporia/plugins/responses/buckling.py` | `buckling_load`. As objective: maximise the lowest load factor through a KS or p-norm aggregate of 1/λ of the lowest few modes. As constraint: λ₁ ≥ λ_min, normalised to ≤ 0. |
| `toporia/plugins/problems/column_buckling.py` | Preset with the paper's compressed column. |
| `tests/plugins/test_buckling.py` (114 lines) | Euler-load check, finite-difference check of the sensitivity, preset run. |
| Edits to `framework/parts/physics.py` (a BUCKLING section), `tests/apps/test_gui.py`, `plugins/LIBRARY.md`, and the READMEs and `__init__` docstrings of models, physics, problems and responses | Docs and registration. |

**Steps to finish it:**

1. **Rebase onto `integration/physics`.** `wip/buckling` is based on `021a260`, before heat,
   vibration, local stress and non-linear were added. Expect conflicts in the files above,
   because the other physics edited the same places. The rule: keep both sides.
   - `physics.py`: keep every feature section.
   - `tests/apps/test_gui.py`: the reachability test on `integration/physics` already loops
     over every preset, so a buckling preset is covered automatically. Keep that version, plus
     at most a constraint-row step like the one the vibration part added.
   - Recount the README status lines; don't trust either side's number.
2. **Run it:** `python -m pytest tests/plugins/test_buckling.py`, then
   `python -m toporia check model:q4_buckling` and `python -m toporia check response:buckling_load`.
3. **Expect problems in the sensitivity.** The hard part is the adjoint term: λ depends on u
   through K_σ(u), so dλ/dρ = φᵀ(∂K/∂ρ + λ ∂K_σ/∂ρ)φ (explicit part), plus an adjoint solve for
   the dependence of K_σ on u. Check it against central finite differences **at a design with
   well-separated modes**. Near repeated eigenvalues the derivative does not exist. The paper
   derives the adjoint in its sensitivity section; follow it exactly.
4. **Check the physics:** a uniform pinned or cantilever column must give the Euler load
   P_cr = π²EI/(K L)² within a few percent on a reasonable mesh. Note the sign convention of
   K_σ: compression must give positive λ.
5. **Pick an updater:** use one that takes extra constraints (`mma` handles only the volume).
   Use `mmapy_mma`, `pymoto_mma` or `nlopt_mma`, and set the preset's method accordingly.
6. **Docs:** in the LIBRARY.md "To add next", remove buckling from the line "Eigenfrequency,
   then linearised buckling". Eigenfrequency is already done, so drop the line entirely.
7. **pyMOTO has no buckling module**, so there is no pyMOTO cross-check. The docs should say so.

## 4. Done in this round (for context, don't redo)

| Part | Where | Notes |
| :-- | :-- | :-- |
| Heat conduction | `physics/q4_heat.py`, `h8_heat.py`, `_conduction.py`; models `q4_heat`, `h8_heat`, `pymoto_heat`; response `thermal_compliance`; preset *Heat Sink* | Matches pyMOTO to 1e-9. OC now accepts `thermal_compliance`. Supports = T = 0, load `Fmag` = heat input, physics Param `heat_source`. |
| Vibration | `physics/q4_dynamic.py`; models `q4_dynamic`, `pymoto_dynamic`; responses `eigenfrequency`, `eigenfrequency_limit`, `dynamic_compliance`; preset *Vibrating Beam* | Features MODES and HARMONIC. |
| Local stress (augmented Lagrangian) | `responses/local_stress.py`, `updaters/augmented_lagrangian.py`; preset *L-bracket (local stress)* | `local_stress` returns a penalty, not a ≤ 0 constraint. It declares `only_with_updaters = ("augmented_lagrangian",)`, and `framework/parts/composition.py::_check_response_updaters` refuses any other updater. |
| Large deformation | `physics/q4_nonlinear.py`; model `q4_nonlinear`; response `end_compliance`; preset *Nonlinear Cantilever* | Newton with load steps; energy interpolation in void. The preset's non-linearity is mild: larger loads make grey designs snap, and load control cannot follow that. `checks/model.py` honours a `check_load_scale` attribute for this. |

## 5. Still to add: small (one file in an existing slot)

| Item | What to do | Source |
| :-- | :-- | :-- |
| Anisotropic PDE filter | Extend `filters/pde.py` with a direction-dependent radius (a tensor r² in −∇·(r²∇ρ̄) + ρ̄ = ρ). Add a new filter or a Param. Adjoint check. | Lazarov & Sigmund, *IJNME* 86 (2011), https://doi.org/10.1002/nme.3072 |
| Moving morphable voids (MMV) | A representation like `representations/mmc.py`, but holes carved from a solid domain (the dual of MMC). Not element-wise, so test with `q4+mma`. | Zhang et al., *CMAME* 322 (2017), https://doi.org/10.1016/j.cma.2017.05.002 |
| Floating projection | An updater that reaches 0/1 designs without β continuation. | Huang, *Eng. Struct.* 2020, https://doi.org/10.1016/j.engstruct.2020.110330 |
| Simulated annealing | A deliberately weak gradient-free baseline. Cap the evaluations. It will probably fail the 10 %-of-OC benchmark: report that, don't register a failing part, and don't weaken the check. | topASA on GitHub |
| Compliant mechanism + force inverter | A response that maximises output displacement u_out = lᵀu with springs at input and output, using the existing `adjoint()` / `mutual_energy()` of the STRESS feature. Springs need a scenario or physics addition (stiffness on the diagonal at the ports). Then the force-inverter preset. Use MMA (signed sensitivities). | Sigmund, *Mech. Struct. Mach.* 25 (1997), https://doi.org/10.1080/08905459708945415 |
| pyMOTO mechanism module | Optional cross-check for the compliant mechanism, as `pymoto_heat` and `pymoto_dynamic` do for theirs. | pyMOTO |
| Reference results from the original MATLAB codes | Optional. The owner chose gradient checks only for now. If wanted later: run top88, top99neo, top3d, TOBS, MMC and the level-set codes once in GNU Octave, and store the numbers as test references. Ask the owner first: installing Octave needs approval. | see `toporia/plugins/SURVEY.md` |

## 6. Still to add: medium (new physics or a whole method)

| Item | What to do | Source |
| :-- | :-- | :-- |
| **Linearised buckling** | **Section 3 above.** | Ferrari, Sigmund & Guest 2021 |
| Geometry projection | A representation of bars with round ends, projected through a signed distance, with a size variable per bar that can switch it off. Python reference code: `pygpto` (Norato). | Norato, Bell & Tortorelli, *CMAME* 2015, https://doi.org/10.1016/j.cma.2015.05.005 |
| Reaction–diffusion level set | A whole method like `methods/levelset_rbf.py`. Nucleates holes and needs no re-initialisation. | Otomori et al., *SMO* 51 (2015), https://doi.org/10.1007/s00158-014-1190-z |
| Hamilton–Jacobi level set; topological derivative | A whole method. | Challis, *SMO* 41 (2010), https://doi.org/10.1007/s00158-009-0430-0 ; Amstutz & Andrä, *JCP* 2006, https://doi.org/10.1016/j.jcp.2005.12.015 |
| Phase field | A whole method, or a regularising response. Allen–Cahn / Cahn–Hilliard; no filter needed. | Bourdin & Chambolle 2003, https://doi.org/10.1051/cocv:2002070 ; Takezawa et al. 2010, https://doi.org/10.1016/j.jcp.2009.12.017 |
| Explicit length scale, machining, self-support | Constraint responses on filtered fields (Zhou), a directional accessibility filter (Langelaar 2019), and a projection-based overhang filter (Gaynor & Guest). | https://doi.org/10.1016/j.cma.2015.05.003 , https://doi.org/10.1016/j.cma.2019.03.037 , https://doi.org/10.1007/s00158-016-1551-x |
| Multi-resolution design and analysis meshes | A fine design field over a coarse FE mesh. Probably a representation plus a model option. Watch for checkerboard artefacts. | Nguyen et al., *SMO* 41 (2010), https://doi.org/10.1007/s00158-009-0443-8 |
| Neural reparameterisation (TOuNN) | A representation whose variables are network weights, with the `adam` updater (already in). Needs PyTorch or JAX, which may have no Python 3.14 wheels on Windows: check first and report. | Chandrasekhar & Suresh, *SMO* 63 (2021), https://doi.org/10.1007/s00158-020-02748-4 |
| SINH and Hashin–Shtrikman material laws | Need a small framework change: the material law must also see the volume (SINH) and Poisson's ratio (HS). Currently `Interpolation.stiffness(ρ, E0, Emin)` only. | Bruns 2005, https://doi.org/10.1007/s00158-005-0537-x ; Bendsøe & Sigmund 1999, https://doi.org/10.1007/s004190050248 |

## 7. Small fixes noticed (from `toporia/plugins/TODO.md`)

- The console's `obj=` column prints the change since iteration 1 (`engine/loop.py`), which reads
  like a negative compliance. Rename it `Δobj`, or print the objective.
- `--set 'representation={...}'` with a JSON value that arrives as a plain string (PowerShell 5.1
  strips the quotes) crashes in `engine/pipeline.py`. Give a clear error instead.
- The L-bracket dimensions and load point were written from memory. Check them against Le et al.
  2010.

## 8. When you finish a part

Run its tests, `tests/apps/test_gui.py`, `tests/checks` and `tests/golden`, then the full suite
once. Commit on `integration/physics` (or a branch off it). Tell the owner what was done and
what wasn't, with the numbers.
