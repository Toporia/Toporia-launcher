# `toporia/apps` — the desktop app and the command line

Neither contains optimisation logic. Both turn what the person chose into a
[`Run`](../framework/problem/run.py) and hand it to the [`engine`](../engine/README.md).

```
apps/
├── cli.py            toporia run · compare · sweep · check · list · export  (no command: the GUI)
└── gui/
    ├── app.py        starts Qt (and sets matplotlib's Qt backend first)
    ├── window.py     the main window: lays out the panels, wires the Run/Stop button
    ├── canvas.py     the live density image and convergence curve
    ├── config.py     the panels' values → a Run (cheap, so the Pipeline box can refresh)
    ├── runner.py     calls the engine's modes and routes their printed output to the log
    └── panels/       every input panel, one module each
        ├── method.py     mesh, volume, and the method: physics model + updater, or whole
        ├── pipeline.py   the Pipeline box
        ├── specs.py      filters, objective, constraints
        ├── loads.py      load cases
        ├── modes.py      the settings of each analysis mode
        ├── forms.py      a form generated from Param declarations
        └── common.py     small shared widgets and helpers
```

```mermaid
flowchart LR
    person(["person"]) --> window["window.py"]
    window --> panels["panels/<br/>generated from the plugins'<br/>Param declarations"]
    panels --> config["config.py<br/>values → Run"]
    config --> pipelinebox["Pipeline box<br/>(engine/pipeline.py)"]
    window -- "Run" --> runner["runner.py"]
    runner --> modes["engine/modes"]
    modes -- "on_iteration" --> canvas["canvas.py<br/>live design + curve"]
    modes -- "print()" --> log["log box"]
    window -- "Stop: raises in on_iteration" --> modes
```

Every input that comes from a plugin — a method's, filter's or response's parameters,
the list of models, updaters, filters, objectives, constraints — is generated from the
plugin classes, so a new plugin appears in the GUI and the CLI without editing anything
here. A plugin whose optional package is not installed is shown greyed out with the
install command.
