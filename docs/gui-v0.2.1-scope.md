# GUI v0.2.1 — accepted scope

Source: user discussion and clarifications, 27 October 2026. This records
requirements and implementation checkpoints. It supersedes conflicting earlier
GUI design assumptions.

## Interface and navigation

- Make Home much sleeker: a few large entry points, minimal visible content.
  Benchmarks and Function Explorer are separate sections; move benchmark cards
  inside their section.
- Group controls into clear boxes, with larger buttons, icons and panels that
  can be collapsed and expanded. Reveal updater settings on selection.
- Show the Run button only in the third step (Runner), not globally or in other
  steps. Confirmed: Runner may contain other controls and results.
- Preserve detailed requirements, decisions and implementation tracking.

## Functions, library and nested networks

- A function is a computational method. The integration branch contains methods
  to expose later; the present library uses built-in, implemented methods.
- Initially expose one representative method per computational stage, except
  the editor and initial problem definition. Implemented filters can offer more.
- A left-hand library lists functions compatible with the current context.
- Entering/zooming into a node makes its contents the main workspace. Show
  incoming data/contracts at the top, expected output at the bottom, and the
  local network in the middle. Users can add library blocks within sub-blocks.
- At the top level include operating-space definition, optimization loops,
  composition functions and terminal export functions. Explain unassociated
  modules and which functions can contain other functions.
- Prepare Function Explorer infrastructure and contextual help explaining each
  region, method and computation. Structure knowledge for later researcher input.
- Document how developers add functions now; GUI function authoring is future work.

## Composition

- Sequential: use an explicit transformation function between optimization
  stages. First transformation restricts the next design space to the previous
  optimized volume.
- Parallel: branches share an input domain, each containing its own physics and
  computational subfunctions. Finish branches independently before combining
  their outputs. Label this execution/data-transfer behavior on arrows.
- Offer union, intersection and difference combination operations.
- Every pipeline ends with an export function.
- Fix arrowhead geometry after moving nodes: orient the head to the terminal
  direction of its connector and preserve its shape/angles.
- Coupled solving and combination during every optimization iteration are future
  work, not v0.2.1 requirements.

## Results, post-processing and export

- Separate post-processing (modifying a result) from export (writing files to
  another location). Export version control is future work.
- Initial post-processing is a simple hard binary threshold at 0.5. Adopt
  density >= 0.5 -> 1, density < 0.5 -> 0 as the implementation boundary rule.
- Each manually executed post-processing step refreshes the displayed result.
- Initially expose volume fraction, iteration count, and objective value. Name
  and explain the selected objective rather than displaying an unlabeled value.
- Allow statistics to be shown/hidden and their graphs enabled/disabled.
  The optional iteration visualization is a progress bar against maximum
  iterations; hide that bar by default.
- Make result display smoother. Allow live display updates to be turned on/off
  and set an update interval, defaulting to every iteration (interval 1).
- Maximum local stress and price are future statistics; the user's example
  price model is scaled volume fraction plus an initial offset.

## Appearance (added to current scope)

- Add a persistent appearance selector: Basic and Sleek monochrome.
- Basic: plain, inexpensive Qt controls, minimal decoration, no animated effects.
  Windows 95 is a visual reference, not a requirement for exact reproduction.
- Sleek: black surfaces, white text, thin borders, clear focus/selection states.
- Style controls, network graphics and result plot surrounds consistently;
  preserve meaningful scientific result colors and legibility.
- Ordinary Qt styling should suffice; custom GPU shaders are not required for
  this requested appearance. Revisit only if actual visual effects require them.
- Preliminary source review: app.py sets Qt Fusion; method_view.py has hardcoded
  scene colors; canvas.py styles plot backgrounds separately. A complete switch
  needs coordinated styling and visual verification across workspaces.
- The user moved both appearance modes into current implementation after the
  initial deferral. View > Appearance changes the application-wide setting;
  it persists independently of projects. Basic uses plain Qt Fusion controls;
  Sleek uses black backgrounds, white chrome/text/icons and thin borders.
- Controls, network scenes, 2D editor chrome, optional 3D viewport chrome,
  benchmark preview backgrounds and embedded plot surrounds share the mode.
  Physical support/load colors and scientific result data retain their meaning.

## Implementation checkpoints

Work on branch `gui-v0.2.1` in `toporia-gui`; do not edit integration or launcher.
The user authorized implementation with "GO" on 27 October 2026. Earlier
gui-plan.md checkpoints describe v0.2 and remain historical context.

- [x] Capture accepted scope, create version branch and confirm Run placement.
- [x] Simplify Home, build registry-backed Function Explorer and fix Run placement.
- [x] Contextual method controls, nested network navigation/library and arrows.
- [x] Separate post-processing/export and refresh manually processed results.
- [x] Selectable statistics/graphs and configurable live display updates.
- [x] Executable sequential/parallel composition with Boolean combination.
- [x] Basic / Sleek monochrome appearance switch, persistence and verification.
- [x] Persistence, documentation, regression and visual verification.

## Merge with the integration work (branch `full-gui`, 29 October 2026)

"Expose later" is now: the GUI shows every function the integration branch added.

- [x] Merge `gui-v0.2.1` and `feature/research-presets-v022`; both sides' fields
  (`Scenario.point_springs` and `regions`) and post-processing arguments kept.
- [x] Method library lists every updater, whole method, representation, physics
  model, material law, objective and constraint; incompatible ones greyed out
  with the reason. Method inspectors no longer hide all but one entry.
- [x] Runner offers every study mode (the worker already ran all of them).
- [x] Post-process: the full post-processor list beside the 0.5 threshold, applied
  after every run or on demand. Export lists every registered exporter.
- [x] Home library split into Benchmarks, Paper figures and Research showcases.
- [x] Copy to custom works for every preset: heat conduction reads custom
  regions (sinks, heat inputs, no load needed); load holes load their ring.
- [x] Every preset opens and walks all five steps without an error; custom copies
  give the preset's first objective (except Drone Arm, see To do).

## Architecture review and implementation notes

The earlier graph described a fixed Run rather than driving execution. v0.2.1
adds an explicit validated workflow tree, independent stage settings, shared
physical-domain/mesh contracts, nested navigation and a headless executor.
Workflow configuration has its own project field, separate from view state;
legacy development snapshots migrate without discarding the execution tree.

Sequential restriction uses actual problem void bounds and a material budget
relative to the allowed preceding volume. Initial restriction supports composed
methods with element densities and no variants. Empty/invalid domains are
refused, and unsupported restricted stages are identified before execution.
The mesh remains shared; arbitrary remeshing/transfers are outside this version.

Parallel branches are independent in their data flow and scheduled consecutively
to bound peak memory. Their completed results are combined at 0.5. Union,
intersection and first-minus-others difference are implemented. Boolean output
is not claimed to have a single evaluated objective or proven feasibility.
Each stage keeps separate exact density/provenance/history files.

Nested composition is typed and acyclic; arbitrary free rewiring/cycles are not
enabled. This provides the requested simple initial framework without implying
that any visually drawn connection can compute. Function creation remains a
documented plugin extension path, with GUI authoring on the future list.

The prior 20–40 developer-day estimate was a pre-inspection planning range, not
a measured duration. Core v0.2.1 implementation is now present; the substantial
remaining items are the separately deferred authoring interface, coupled
physics, export version control and integration of additional computational
methods. See gui-workflow.md and gui-function-development.md for usage/contracts.

## Validation record

- Initial applications/engine/golden regression: 288 passed.
- Full suite: 650 passed, 1 skipped; 8 checks failed exclusively while cleaning
  temporary directories in the Windows sandbox's system-temp location.
- Re-ran all 8 affected postprocessor/guide checks with TEMP/TMP in the workspace:
  all 8 passed. No numerical baselines were changed to resolve those failures.
- Final applications/engine/golden regression after appearance integration:
  **295 passed**. This includes real Qt worker processes, saved nested workflows,
  actual sequential solves and domain-mask enforcement, Boolean operations,
  processed-array and STL export ownership, contextual click/reopen behavior,
  project migration and appearance persistence/data preservation.
- The last focused appearance round-trip check passed both tests, including
  dark/light density contrast without changing the underlying density array.
- Final focused v0.2.1 interaction/appearance/export smoke check: **9 passed**.
- Ruff passed for all changed Python source/test files; git diff --check passed.
- Offscreen visual review covered Home, Function Explorer, root/nested/parallel
  networks, Runner, Post-process, Export and processed results in both modes.
  Windows fonts were loaded explicitly because the offscreen plugin otherwise
  exposes no font families on this host. Live GPU rendering of the optional VTK
  viewport was not exercised by those offscreen captures.

Local visual previews are in results/v021-previews/ (ignored generated outputs).
For conformance checks in this sandbox, set process-local TEMP and TMP to an
existing directory under results/ and use pytest --basetemp=results/<unique-name>.
