# Research functions and figure presets

This is the V0.2.2 research track, alongside the GUI work. Start with the
[visual mathematical guide](core.html), [Markdown source](core.md),
[function coverage](coverage.md), or [Batch 1 report](batch-1.md).
The [complete module map](modules.md) identifies numerical implementation files,
supporting modules and preset recipes.

[Batch 2 report](batch-2.md) · [Case index](batch-2-cases.md) ·
[Figure gallery](evidence/batch2/index.html). Four new comparisons match identified
source targets; unresolved cases and a numerical saturation failure are explicit.

[Batch 3 report](batch-3.md) · [Case index](batch-3-cases.md) ·
[Figure gallery](evidence/batch3/index.html) · [Optimization math](optimization.html).
Thirty-one additional companions document updaters, representations and level
sets. Their paper reproductions remain unresolved, with specific differences
and failed feasibility recorded separately from passing execution checks.

[Batch 4 report](batch-4.md) · [Case index](batch-4-cases.md) ·
[Gallery](evidence/batch4/index.html) · [Framework assessment](framework-assessment.html).
All 97 currently inventoried numerical functions/engines now have an example
or engineering record. Most full paper reproductions remain unresolved;
coverage, numerical verification and source matching are separate facts.

Every research preset pairs a runnable setup with a short explanation of the
function, typeset equations, symbol definitions, source figure and comparison
scope. Its existing preset **?** opens the explanation. The same content exports
as standalone HTML; no web connection, JavaScript or TeX installation is needed
to view its equations. The original general-purpose presets remain intact.

The [18 original preset descriptions](presets/originals/index.html) now explain
their own configurations and core mathematics through the same Help button.
Their recipes remain unchanged and are not relabeled as paper reproductions.

## Run the first examples

```powershell
python -m experiments.research_figures
python -m experiments.research_inventory
```

The first command runs both selectable Figure 3(a) research presets and compares
against the captured unchanged author code in
[`paper_top88.json`](../../tests/references/paper_top88.json). It writes physical
density, history, comparison images, descriptions and machine-readable reports
under ignored `results/research/top88/`. A failed numerical match exits nonzero
and writes the attempt under `to-fix/`. Tracked summaries and small review images
live here; ordinary generated run output is disposable.

Fresh original captures are optional and need an existing MATLAB installation:

```powershell
python -m experiments.research_figures --capture-original --source-dir PATH --matlab-exe PATH
```

Supply the unchanged author `top88.m` linked in the fixture. The driver checks
its SHA-256, isolates MATLAB preferences in a temporary workspace and extracts
the final physical fields from the author's plots. It installs nothing and
never rewrites a reference fixture. Review a new capture before promoting it.

## Status and contribution rules

See [conventions](conventions.md), the [preset template](templates/preset.md),
the [researcher contribution template](templates/research-note.md) and the
[`to-fix` queue](to-fix/README.md).

The inventory separates **98 selectable functions/engines** from **92 presets**
(18 original and 74 registered research recipes). The volume-preserving
projection companion was quarantined until its 0/1-design limit was settled;
it is registered again. One example can demonstrate several
functions. Metadata citations are starting points; pending rows are not claims
of paper review or successful reproduction.

## GUI handoff

This branch owns `apps/research_render.py`, `apps/gui/research_help.py` and the
small `problem_topic()` hook in `apps/gui/help.py`; it does not modify
`toporia-gui`. `problem_description(name)` returns the optional plain description.
The existing `problem_info(name)` tuple stays compatible.

For later integration, the GUI owner can link benchmark cards and Function
Explorer to those descriptions, show target/evidence status, and navigate to
comparison figures. See [GUI handoff](gui-handoff.md) for file ownership and
follow-up tasks. Nested network design remains with that effort.
