# GUI handoff and file ownership

Research work lives in `toporia-integration`, branch
`feature/research-presets-v022`. The colleague's `toporia-gui` checkout has only
been inspected. The GUI framework, nested network, library widgets and
navigation remain with that effort.

## Integration surface delivered here

- `plugins/problems/_research.py`: plain immutable explanation data.
- Presets declare `DESCRIPTION`; no GUI imports in numerical/preset code.
- `plugins/problems.problem_description(name)`: description or None.
- `apps/research_render.description_html(description)`: escaped content and
  local embedded MathText PNGs, usable in a QTextBrowser.
- `apps/gui/research_help.ResearchHelpTopic`: existing topic title/sections
  plus rendered scientific description.
- `apps/gui/help.py`: only the preset-topic hook. Merge this small function
  change carefully if the colleague edits help.py later.
- `problem_info(name)` and short ABOUT/REFERENCE text are unchanged.

## GUI follow-ups after this batch

1. Add a Description / Math action to research benchmark cards, calling the
   existing help topic so there is a single content source.
2. Link Function Explorer entries to presets using `description.functions`.
3. Show the target paper/panel and separately sourced reproduction statuses.
   DESCRIPTION describes the intended comparison; a report supplies its result.
4. Link comparison images and make pending/to-fix states visibly distinct.
5. Check image scaling, scrolling, narrow windows and both GUI themes after merge.
6. Connect the same description data to future nested functions without
   changing numerical ownership or inventing a new computational contract here.

Existing test-isolation note: selective reruns of the post-processing and method
sweep tests can inherit a 3-D `_base_cfg` from a shared MainWindow fixture while
its preset combo still says MBB. Fresh-process runs pass. Keep explicit fixture
resetting in mind when restructuring GUI tests; this batch leaves those files alone.

The research renderer requires no network or TeX installation. Known original presets now receive mathematical descriptions through the Batch 4 fallback; unknown/plugin presets without DESCRIPTION retain ordinary help.

## Batch 2 additions

Twenty further registered research companions carry descriptions. Transfer and
constitutive figures remain experiment outputs; ordinary GUI Run performs the
documented optimization companion. The gallery and structured reports are under
`docs/research/evidence/batch2/`. Future card/Function Explorer links can use them.

Keep numerical checks, equation/curve agreement, visual paper review and unresolved
targets separate when displaying status. The volume-preserving-projection recipe
is quarantined: its saturated-input adjoint can become undefined. Do not expose
that companion as ready until the numerical/compatibility issue is resolved.
The existing underlying mode remains unchanged by this documentation batch.

## Batch 3 additions

Thirty-one more presets provide mathematical descriptions for 30 functions:
22 remaining updaters, five further representations (MMC also has a separate
variable-thickness example), and three standalone level sets. OC and element
densities reuse Batch 1. All new paper reproductions are unresolved; the
[gallery](evidence/batch3/index.html) and structured reports record this explicitly.

Later GUI cards should display execution, feasibility, convergence, source
review and paper matching as separate facts. A finite run or a library success
flag is not a paper match or feasibility certificate. Local stress and
multi-constraint OC companions retain failed stress limits in their evidence.
The numerical framework, library/canvas and colleague checkout are unchanged.

## Batch 4 additions

Nineteen further presets explain the remaining physics/responses and two grouped
post-processing demonstrations. The groups reuse saved fields for seven 2D
operations and STL export; GUI Run is the documented ordinary optimization
companion. The existing Post-processing panel selects actual output operations.
No preset-to-Output adapter or new GUI execution mode was introduced.

The [framework assessment](framework-assessment.html) lists concrete contracts
for future typed ports, shared variables, transfers, derivative joins and cache/
worker lifetimes, with estimates in hours of agent execution. The GUI can reuse
the delivered knowledge now; execution of a general network remains separate.

Expose physical units and objective meaning: an eigenvalue-normalized objective,
signed port displacement, nonlinear end compliance and thermal compliance are
not interchangeable with static compliance. Keep source matching, independent
numerical checks, feasibility and iteration caps separate. Current coverage has
no untouched rows; it still has unresolved paper comparisons and known variant
limitations. No release tag or colleague-checkout change is made here.

The description API also supplies mathematical help for the 18 known original presets through `_research_defaults.py`, with no recipe changes or GUI imports. Explicit `DESCRIPTION` takes precedence; unknown/plugin presets retain the optional fallback. All current presets now have structured mathematical help. The short ABOUT/REFERENCE tuple and existing help sections remain compatible.
