# GUI v0.2.1 — accepted scope

Source: user discussion and clarifications, 27 October 2026. This records
requirements, not completed implementation. It supersedes conflicting earlier
GUI design assumptions. Implementation/code review follows scope capture.

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

## Future appearance task

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
- Rough effort: 1–3 developer days; defer to future to-do list as requested for
  larger appearance work. This is an estimate, not a measured performance claim.

## Implementation checkpoints

Work on branch `gui-v0.2.1` in `toporia-gui`; do not edit integration or launcher.
The user authorized implementation with "GO" on 27 October 2026. Earlier
gui-plan.md checkpoints describe v0.2 and remain historical context.

- [x] Capture accepted scope, create version branch and confirm Run placement.
- [ ] Simplify Home, build registry-backed Function Explorer and fix Run placement.
- [ ] Contextual method controls, nested network navigation/library and arrows.
- [ ] Separate post-processing/export and refresh manually processed results.
- [ ] Selectable statistics/graphs and configurable live display updates.
- [ ] Executable sequential/parallel composition with Boolean combination.
- [ ] Persistence, documentation, regression and visual verification.

Other defaults above are implementation assumptions where exact details were
not specified. Detailed architecture review is still needed before revising
the overall implementation estimate. The existing graph is a read-only
description of a Run, not yet an execution graph: composition needs an explicit
validated execution contract, not only additional graphical connections.
