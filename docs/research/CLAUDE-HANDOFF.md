# Message for Claude: research-track handoff

Claude, continue from `C:\Users\johan\Documents\GitHub\toporia-integration`,
branch `feature/research-presets-v022`. Read any applicable repository instructions
before editing. This is the research/documentation track alongside another GUI
workstream. The four batch commits are:

- `209b2cf`: foundation, core math guide and top88 examples.
- `3280ca7`: filters, material laws and continuation.
- `eeda046`: optimizers, representations and level sets.
- `479c051`: remaining physics/responses/post-processing and framework assessment.

## What completion actually means

There are 97 inventoried numerical functions/engines and 90 presets. All current
functions have an example/evidence record; all presets have structured mathematical
help. There are 72 research recipes and 18 original general-purpose presets.

This is **example/documentation coverage**, not complete research validation.
The census has eight baseline-function examples, four verified research-function
examples, four own engineering examples and **81 functions with unresolved paper
comparisons**. These are function counts, not counts of independently reproduced
papers or figures. Batches 3 and 4 certified no new full paper-figure reproduction.
Many demonstrations use own diagnostic inputs or declared numerical variants;
exact original-paper settings were not recovered for every case.

The final credit limit shortened final audit/polish. The scientific backlog mostly
already existed before that limit. Numerical guards and golden baselines were not
relaxed to hide it. Do not translate “no pending census rows” into “nothing left.”

## Read first

1. [Research overview](README.md), [coverage](coverage.md), [inventory](inventory.json).
2. [Core computation](core.md), [variable/update guide](optimization.md).
3. [Batch 4 report](batch-4.md), then earlier batch reports for provenance.
4. [To-fix index](to-fix/README.md) and each relevant case's `report.json`/README.
5. [GUI handoff](gui-handoff.md) and [framework assessment](framework-assessment.md).

## Priority 1: audit the last additions and keep readiness claims honest

- Review `toporia/plugins/problems/_research_defaults.py`. It supplies descriptions
  for the 18 original presets using shared model equations and actual recipe data.
  This is a pragmatic fallback, not 18 independently authored mathematical monographs.
  Check equation roles, symbols, normalization and parameter assumptions for each
  preset. In particular, distinguish an objective from a similarly named constraint,
  and keep shared SIMP/model formulas consistent with the selected configuration.
  Long setup text currently includes Python-style dataclass/dictionary representations;
  readability and per-preset explanations can be improved without changing recipes.
- Audit the new public description fallback in `plugins/problems/__init__.py`.
  Explicit DESCRIPTION wins, known originals receive generated help, and unknown
  presets can still return None. Keep this compatible with future/plugin presets.
- Inspect actual Help windows in normal themes and narrow windows. Qt equation
  resources and representative offscreen screenshots were checked; comprehensive
  manual interaction, accessibility and theme review were not completed.
- Many physics companions deliberately stop at 20 or 60 iterations; Batch 3 has
  other caps. Small motion, a library finish flag, finite output and passing a
  derivative check are not interchangeable with feasibility/convergence.
- Batch 4's stress-volume and minimum-length runs retain failed extra constraints.
  Batch 3 retains volume overshoots, gray neural fields and failed stress limits.
  Keep these visible; do not silently promote these presets to “validated design.”

## Priority 2: concrete numerical/reproduction issues

| Issue | Evidence / next action |
| :-- | :-- |
| ~~Volume-preserving Heaviside adjoint becomes non-finite on saturated all-solid fields~~ | **Resolved 28 Oct 2026:** identity limit for uniform 0/1 designs, explicit error for mixed ones, companion registered. See `to-fix/batch2-heaviside_volume/README.md`. |
| Multiresolution analysis can be artificially stiff | `evidence/batch4/multires/report.json`: coarse compliance 235.9407 versus independent fine-Q4 791.4156 on the same density. Investigate discretization/length control and source alignment; preserve independent fine analysis as a required comparison. |
| PTO is a different algorithm from original PTOc | `evidence/batch3/pto/paper-attempt/report.json`: author 170 iterations, current variant capped at 600, fresh C 266.609374 versus 323.297382 (+21.26%). Current allocation uses negative filtered sensitivity; the author uses element compliance and filtered redistribution. Parameter tuning does not remove that formulation difference. |
| Sharp continuation companions can perform poorly | Batch 2 report and schedule case records: caps, oscillation and very poor geometric-beta OC behavior remain. Align updater/trigger rules before claiming source trajectories. |
| Source implementations differ from many current variants | MMC/MMV unions/sampling/geometry, tanh neural field versus TOuNN, SiMPL normalization/step policy, RBF/HJ/RD level sets, FE heat versus FVM, buckling p-norm versus source KS, geometric-length and phase-field conventions. Classify intentional variants separately from actual defects. |

If an exact source method is added, declare it as a separate variant where its
behavior differs. Do not overwrite existing algorithms solely to make a paper
comparison look successful. Large new implementations require an agreed scope;
this handoff is not a request to implement the entire external-code backlog.

## Priority 3: finish actual paper reproduction

For each unresolved function, distinguish:

1. Missing source, numbered panel, geometry, loads/supports or parameter inputs.
2. An intentional mathematical/discretization/optimizer variant.
3. A numerical defect or unconverged/infeasible run.
4. An own engineering tool with no originating paper figure.

Recover one exact source example at a time, declare tolerances before comparison,
record source hashes and compare the right quantities. Most current Batch 4
`paper_visual_status` values are `not_assessed`; publisher abstracts or analytic
checks do not count as inspecting/reproducing a paper panel. The small top3d probe
compares first/last printed compliance and stopping count against an earlier native
capture; it does not compare a native final field or constitute a fresh MATLAB run.

Source/provenance reviews are in each batch's `paper-reviews.json`. Reproduction
drivers, captured arrays and case-level next checks are already present; build on
them rather than starting the census again. Keep failures in `to-fix` with useful
next actions and preserve prior valid evidence.

## Priority 4: strengthen checks where their scope is limited

- Batch 4's own driver probes one smooth directional derivative per response/budget/
  constraint, holding mutable references/multipliers fixed. Its gate is 3e-3; recorded
  errors passed the tighter 1e-4 saved-evidence regression. This is not a complete
  derivative proof at topology switches, repeated modes or all parameter regimes.
  Existing relevant numerical tests were also run.
- Post-processing checks include an independent flood fill, integer thresholded
  volume, simple straight-bar calibration, grayness identity, SVG parsing, DXF
  sections and STL byte count/oriented volume. They do not establish full geometric
  equivalence, watertight/manifold meshes in every contact case, manufacturability
  or post-smoothing structural performance. Add meaningful independent checks
  where a specific export/performance claim is needed.
- A complete combined-repository test run after GUI integration remains to do.
  Batch 4 ran focused numerical/golden, all preset GUI comparison, help and research
  checks: **395 distinct passing checks**, not the entire repository test suite.
- Default Windows Tk is incomplete here. One plot test was rerun successfully with
  process-local `MPLBACKEND=Agg`. Use workspace-local TEMP/TMP and pytest basetemp;
  do not change global installations or numerical baselines as a workaround.

## GUI work still owned by the other workstream

The existing preset Help hook is delivered. Future GUI work still includes the
left function library, nested canvas, zoom/collapse/connect navigation, regional
help/Function Explorer presentation, function-to-preset/evidence links and separate
badges for execution, feasibility, convergence and source matching. Descriptions
and reports are ready to feed those views. Preset Run usually executes an ordinary
optimization companion; transfer curves and saved-field exports can instead require
the explicit experiment command. Do not imply the GUI already executes a general
nested research graph.

Do not modify the colleague's `toporia-gui` checkout without coordinating ownership.
The framework assessment is a design/effort assessment only. Typed ports, shared
variable ownership, transfer adjoints, derivative joins, cache invalidation, coupled
state execution, independent material phases and unstructured meshes are not delivered
merely because their requirements are documented. Its hour ranges are estimates of
agent execution, not benchmarked guarantees.

## Repository hygiene and practical commands

The checkout intentionally still has pre-existing user/other-work changes in root
README.md, `docs/INTEGRATION-progress.md`, and untracked `docs/research-origins/`.
Preserve them. Do not stage/reset/clean these blindly. No release tag was created.

Project Python:
`C:\Users\johan\AppData\Local\Python\pythoncore-3.14-64\python.exe`.
Relevant drivers are `experiments.research_batch2`, `research_batch3`,
`research_batch4`, their publishers and `research_inventory`/`research_docs`.
Read CLI help and recorded scopes before running; some all-case/strict-paper
commands deliberately exit nonzero for known failures/unresolved comparisons.
Do not repeatedly rerun all expensive examples just to refresh descriptions.

Start with a short audit and present the user a prioritized, bounded next batch.
The highest-value unfinished work is scientific reproduction/known limitations
and precise explanations, not increasing the raw number of presets.
