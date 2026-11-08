# `toporia_gui` — the desktop app

No optimisation logic: it turns what the person chose into a
[`Run`](../toporia_core/framework/problem/run.py) and hands it to the
[`engine`](../toporia_core/engine/README.md), in a separate process
([`worker.py`](worker.py)) working on a snapshot of the project, so the window stays usable.
The command line is part of the core ([`toporia_core/cli.py`](../toporia_core/cli.py)); with no
command it starts this app, found through the `toporia.apps` entry point.

Home opens projects (and recent ones), the benchmark library, the function explorer and the
documentation. The five steps along the top: Problem (the physical definition, editor and
spatial view), Method (the whole computation as a collapsible tree), Runner, Post-process
(the inspector: every run, every field) and Export. Physical objects are meshed by
`framework/problem/regions.py` and `spatial.py`, so the GUI and the command line use the
same forces and boundary conditions. See [the user workflow](../docs/gui-workflow.md) for
file and interaction details.

```
apps/
├── cli.py            the command line; with no command, the GUI
└── gui/
    ├── app.py        starts Qt (and sets matplotlib's Qt backend first)
    ├── window.py     the main window: lays out the panels, wires the Run/Stop button
    ├── canvas.py     the live design and convergence curve; a 3-D view at the end
    ├── config.py     the panels' values → a Run (cheap, so the Pipeline box can refresh)
    ├── runner.py     calls the engine's modes and routes their printed output to the log
    └── panels/       every input panel, one module each
        ├── method.py     volume, and the method: physics model + updater, or whole
        ├── design.py     representation, 2-D or 3-D, resolution and the mesh it gives
        ├── pipeline.py   the Pipeline box
        ├── specs.py      filters, objective, constraints, schedules
        ├── loads.py      load cases
        ├── modes.py      the settings of each analysis mode
        ├── forms.py      a form generated from Param declarations
        └── common.py     small shared widgets and helpers
```

```mermaid
flowchart TB
    panels["panels/<br/>generated from the plugins"]
    config["config.py<br/>the values become a Run"]
    runner["runner.py<br/>starts an analysis mode"]
    canvas["canvas.py · log<br/>live design, curve, output"]
    panels --> config --> runner --> canvas
```

Every input that comes from a plugin — a method's, filter's or response's parameters,
the list of models, updaters, filters, objectives, constraints — is generated from the
plugin classes, so a new plugin appears in the GUI and the CLI without editing anything
here. A plugin whose optional package is not installed is shown greyed out with the
install command.
