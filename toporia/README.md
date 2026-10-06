# `toporia` — the package

Toporia is a platform for topology optimisation in which **every choice is a swappable
part**: how the design is filtered, which physics is solved, what is minimised and
constrained, and how the design is updated. A run fixes the problem and names the parts;
the engine drives them all the same way, so two runs that differ in one part are a fair
comparison.

## Start here

Read in this order; each step is one folder and one README.

1. **What a run is** — [`framework/problem/`](framework/problem/): a `Scenario` (what is
   solved), a `Solver` (how), bundled in a `Run`.
2. **What a part must do** — [`framework/parts/`](framework/parts/): one file per
   interface. [`framework/README.md`](framework/README.md) explains them together.
3. **Which parts exist** — [`plugins/`](plugins/README.md): the catalogue, one folder per
   kind, each listing what is implemented here and what exists elsewhere.
4. **How a run is driven** — [`engine/`](engine/README.md): the one loop, what it records,
   and the analysis modes built on it.
5. **How to add a part** — [`docs/writing-plugins.md`](../docs/writing-plugins.md), with a
   worked example of every kind.

## The layers

```mermaid
flowchart TB
    subgraph ENTRY["Ways in"]
        direction LR
        apps["apps/<br/>the desktop app and the command line"]
        api["api.py<br/>the stable imports for plugins"]
        checks["checks/<br/>the conformance test"]
    end

    engine["engine/<br/>the loop, the stopping rule, the records,<br/>and the analysis modes built on them"]

    plugins["plugins/  —  the swappable parts<br/>problems/ · filters/ · physics/ · models/<br/>responses/ · updaters/ · methods/"]

    framework["framework/<br/>what a run is (problem/), what a part must do (parts/),<br/>how outside optimisers connect (optimisers/),<br/>parameters and plugin discovery"]

    other[("plugins in other<br/>installed packages")]

    apps --> engine
    checks --> engine
    engine --> plugins
    engine --> framework
    plugins --> framework
    api --> framework
    api --> plugins
    other -. "entry points" .-> framework
    other -. "import from" .-> api
```

An arrow means "uses". The arrows only point down: `framework` uses nothing else in
Toporia, `plugins` uses only `framework`, and `engine` uses both but is used by neither. A
plugin therefore never depends on how it is driven or displayed.

## What is where

```
toporia/
├── api.py               the stable imports for plugin authors
├── framework/           THE RULES — no mathematics
│   ├── problem/         scenario · mesh · solver · run · files
│   ├── parts/           method · model · updater · composition · physics · response · representation ·
│   │                    filter · interpolation · schedule · variants
│   ├── optimisers/      flat_view · external_loop
│   ├── params.py        every tunable value, declared once
│   └── registry.py      finds plugins: here, in installed packages, or by hand
├── plugins/             THE PARTS — one folder per kind, each with a README
│   ├── problems/        benchmark presets
│   ├── representations/ what the design variables are: element densities, moving morphable components
│   ├── filters/         design → physical density, and back
│   ├── interpolations/  the material law: SIMP, RAMP
│   ├── schedules/       continuation: how a parameter changes during the run
│   ├── physics/         finite-element solvers and the engines built on them
│   ├── models/          what is optimised: an engine + filters + responses
│   ├── responses/       objectives and constraints that compute themselves
│   ├── updaters/        how the design moves (OC, MMA, BESO, SiMPL, SLSQP, ...)
│   ├── methods/         "<model>+<updater>" names, and whole methods (the level set)
│   ├── shared_params.py parameters several plugins share
│   └── catalog.py       every numeric value a setup lets you sweep
├── engine/              RUNNING THINGS
│   ├── loop.py          the one optimisation loop
│   ├── records.py       history, images, the limit check, run.json
│   ├── pipeline.py      names the parts of a run, for the console and the GUI
│   └── modes/           single · sweep · compare · methods · sensitivity · check
├── checks/              the conformance test, one module per plugin kind
└── apps/
    ├── cli.py           toporia run · sweep · compare · benchmark · check · list · export
    └── gui/             app · window · canvas · runner · config · panels/
```

| Path | What it is | Read |
| :--- | :--- | :--- |
| [`framework/`](framework/) | **The rules.** What a run is and what every plugin must do, plus parameter declarations and plugin discovery. No mathematics. | [framework/README.md](framework/README.md) |
| [`plugins/`](plugins/) | **The swappable parts.** Each subfolder is scanned for plugins, so adding one is adding a file. Each folder's README maps its part of the field: what is here, what exists elsewhere, what is paper only. | [plugins/README.md](plugins/README.md) |
| [`engine/`](engine/) | **Running things.** Builds the method from a run, steps it, applies the one stopping rule, records history and `run.json`, checks the limits; and the analysis modes built on that loop. | [engine/README.md](engine/README.md) |
| [`checks/`](checks/) | **The conformance test.** `conformance(MyPlugin)` checks a plugin's interface, its gradients against finite differences and, for an updater, a benchmark against optimality criteria. | [checks/README.md](checks/README.md) |
| [`apps/`](apps/) | **The desktop app and the command line.** Neither contains optimisation logic; both build a `Run` and hand it to the engine. | [apps/README.md](apps/README.md) |
| [`api.py`](api.py) | **What a plugin imports.** The stable names for writing plugins, especially in other packages. | [docs/writing-plugins.md](../docs/writing-plugins.md) |

## The life of a run

From a click on **Run** to the files on disk, and where each step lives:

```mermaid
flowchart TB
    A["Panels in the GUI, a CLI command,<br/>or a JSON scenario + solver"]
    B["Run = Scenario + Solver + Output<br/>method: 'q4+mma'<br/>(framework/problem/run.py)"]
    C["Look up the parts by name<br/>model q4, updater mma, filters, responses<br/>(plugin registries, framework/registry.py)"]
    D["Refuse at once if a part is missing<br/>or cannot do what the scenario asks<br/>(engine/loop.py)"]
    E["Mesh the problem: elements, supports,<br/>loads, fixed regions, bounds<br/>(framework/problem/mesh.py)"]

    subgraph ITER["Each iteration (framework/parts/composition.py)"]
        direction LR
        F["Filters<br/>x → ρ"]
        G["Physics engine<br/>solve ρ → state"]
        H["Responses<br/>objective, constraints,<br/>gradients"]
        I["Filter adjoint<br/>gradients → x"]
        J["Updater<br/>next x"]
        F --> G --> H --> I --> J
        J -- "next iteration" --> F
    end

    K["Engine: record, draw, stopping rule<br/>(engine/loop.py)"]
    L["Check every limit<br/>(engine/records.py)"]
    M[("final_density.png · .csv<br/>run.json: what, how, which code,<br/>how it ended, limits met, solves")]

    A --> B --> C --> D --> E --> ITER
    ITER <--> K
    K --> L --> M
```

The method in the middle can also be a whole method that does its own iteration (the
RBF level set), and the updater can be an outside library running its own loop in a
background thread (SciPy's SLSQP); to the engine they look the same.

## Extending it

| You want to add… | Write | Guide |
| :--- | :--- | :--- |
| an update rule, or wrap an optimiser library | an updater in `plugins/updaters/` | [docs/writing-plugins.md](../docs/writing-plugins.md) |
| a filter or fabrication rule | a filter in `plugins/filters/` | 〃 |
| a new kind of design variable (bars, splines, a network) | a representation in `plugins/representations/` | [plugins/representations/README.md](plugins/representations/README.md) |
| a continuation rule (how a parameter changes during the run) | a schedule in `plugins/schedules/` | [plugins/schedules/README.md](plugins/schedules/README.md) |
| a material law (density to stiffness) | an interpolation in `plugins/interpolations/` | [plugins/interpolations/README.md](plugins/interpolations/README.md) |
| an objective or constraint | a response in `plugins/responses/` | 〃 |
| a new physics or element | a physics engine in `plugins/physics/` and a three-line model | 〃 |
| a benchmark | a preset in `plugins/problems/` | [plugins/problems/README.md](plugins/problems/README.md) |
| any of these, without touching this repository | your own package with an entry point | [docs/writing-plugins.md](../docs/writing-plugins.md#packaging-outside-this-repository) |

Then `toporia check kind:name`, and mark it ✅ in the folder's README.

## How the code is written

- **Every file opens with what it is and how it connects** — a comment header naming the
  file, what it holds, a small diagram where the data flow is not obvious, and the paper
  it implements, if any.
- **Every class and standalone function has a docstring.** Implementations of an
  interface method (`initialize`, `update`, `forward`, `evaluate`, …) do not repeat it:
  the method is documented once, in `framework/parts/`.
- **Comments say why**, or what a non-obvious line does — not what the code already says.
- **Parameters are declared, not read from dictionaries by hand**: a `Param` next to the
  code that uses it, so the GUI, sweeps and validation follow automatically.
- **Results are pinned.** `tests/golden/` stores seven runs bit for bit; a change that moves
  them is either a bug or is said in its commit, with the baseline regenerated.
