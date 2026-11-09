# Toporia's code: three packages

Toporia is a platform for topology optimisation in which **every choice is a swappable
part**: how the design is filtered, which physics is solved, what is minimised and
constrained, and how the design is updated. A run fixes the problem and names the parts;
the engine drives them all the same way, so two runs that differ in one part are a fair
comparison.

The code is three packages, next to each other in the repository:

| Package | What it is | Needs |
| :-- | :-- | :-- |
| [`toporia_core/`](.) (this folder) | The glue every function uses and no function itself: what a run is, what a part must do, the registries, the engine loop and run modes, the conformance checks, `api.py` and the command line. | numpy, scipy; matplotlib only for figures, when installed ([`toporia_core/engine/plotting.py`](engine/plotting.py)); density images are written by [`toporia_core/engine/png.py`](engine/png.py) |
| [`toporia_library/`](../toporia_library/README.md) | Every function: models and physics, updaters, filters, material laws, representations, responses, schedules, post-processors, whole methods, and the presets with their research descriptions. | the core |
| [`toporia_gui/`](../toporia_gui/README.md) | The desktop app. A run never needs it. | the core, the library, PySide6 |

## Start here

Read in this order; each step is one folder and one README.

1. **What a run is** — [`toporia_core/framework/problem/`](framework/problem/): a `Scenario` (what is
   solved), a `Solver` (how), bundled in a `Run`.
2. **What a part must do** — [`toporia_core/framework/parts/`](framework/parts/): one file per
   interface. [`toporia_core/framework/README.md`](framework/README.md) explains them together.
3. **Which parts exist** — [`toporia_library/`](../toporia_library/README.md): the catalogue,
   one folder per kind, each listing what is implemented here and what exists elsewhere.
4. **How a run is driven** — [`engine/`](engine/README.md): the one loop, what it records,
   and the analysis modes built on it.
5. **How to add a part** — [`docs/quickstart.md`](../docs/quickstart.md) to get going in
   minutes, then [`docs/writing-plugins.md`](../docs/writing-plugins.md), with a worked example
   of every kind.

## The layers

```mermaid
flowchart TB
    gui["toporia_gui<br/>the desktop app"]
    library["toporia_library<br/>the swappable parts and the presets"]
    core["toporia_core<br/>framework · registries · engine · checks · command line"]
    gui --> library
    gui --> core
    library --> core
```

An arrow means "uses", and the arrows only point down; a test
([`tests/test_package_boundaries.py`](../tests/test_package_boundaries.py)) enforces it,
for every import, including those inside functions. The core finds the library's parts
and presets, and the desktop app, through entry points declared in `pyproject.toml`,
exactly as it finds parts in any other installed package: it never names them. Inside
the core, `framework` uses nothing else and `engine` uses `framework`.

## What is where

```
toporia_core/
├── api.py               the stable imports for plugin authors
├── cli.py               toporia run · sweep · compare · benchmark · check · list · export
├── toporia_core/framework/           THE RULES — no mathematics
│   ├── problem/         scenario · mesh · solver · run · files · presets (found by name)
│   ├── parts/           one file per interface; AssembledModel and the filter pipeline
│   ├── optimisers/      flat_view · external_loop
│   ├── params.py        every tunable value, declared once
│   ├── registry.py      finds parts: through entry points, or by hand
│   └── registries.py    one registry per kind, and method_class / check_responses
├── engine/              RUNNING THINGS
│   ├── loop.py          the one optimisation loop
│   ├── records.py       history, images, the limit check, run.json
│   ├── pipeline.py      names the parts of a run, for the console and the GUI
│   ├── fields.py        stress, displacement, temperature of a finished design
│   ├── measure.py       the referee every method in a comparison is measured with
│   ├── png.py           PNG images with NumPy alone
│   ├── plotting.py      matplotlib only when it is installed
│   └── modes/           single · sweep · compare · methods · sensitivity · check
└── checks/              the conformance test, one module per kind of part

toporia_library/         THE PARTS — one folder per kind, each with a README
├── problems/            benchmark presets, 2-D and 3-D, with their research descriptions
├── representations/     what the design variables are: densities, bars (MMC), splines, …
├── filters/             design → physical density, and back
├── interpolations/      the material law: SIMP, RAMP, …
├── schedules/           continuation: how a parameter changes during the run
├── postprocessors/      what is made of the finished design: threshold, checks, SVG/DXF/STL
├── physics/             finite-element solvers and the engines built on them
├── models/              what is optimised: an engine + filters + responses
├── responses/           objectives and constraints that compute themselves
├── updaters/            how the design moves (OC, MMA, BESO, SiMPL, SLSQP, ...)
├── methods/             whole methods (the level sets)
├── shared_params.py     parameters several plugins share
└── catalog.py           every numeric value a setup lets you sweep

toporia_gui/             THE DESKTOP APP — app · window · panels/ · inspector · worker · desktop
```

| Path | What it is | Read |
| :--- | :--- | :--- |
| [`toporia_core/framework/`](framework/) | **The rules.** What a run is and what every plugin must do, plus parameter declarations, the registries and plugin discovery. No mathematics. | [toporia_core/framework/README.md](framework/README.md) |
| [`toporia_library/`](../toporia_library) | **The swappable parts.** Each subfolder is scanned for plugins, so adding one is adding a file. Each folder's README maps its part of the field: what is here, what exists elsewhere, what is paper only. | [toporia_library/README.md](../toporia_library/README.md) |
| [`engine/`](engine/) | **Running things.** Builds the method from a run, steps it, applies the one stopping rule, records history and `run.json`, checks the limits; and the analysis modes built on that loop. | [toporia_core/engine/README.md](engine/README.md) |
| [`checks/`](checks/) | **The conformance test.** `conformance(MyPlugin)` checks a plugin's interface, its gradients against finite differences and, for an updater, a benchmark against optimality criteria. | [toporia_core/checks/README.md](checks/README.md) |
| [`toporia_gui/`](../toporia_gui) | **The desktop app.** No optimisation logic: it builds a `Run` and hands it to the engine, in a separate process. | [toporia_gui/README.md](../toporia_gui/README.md) |
| [`api.py`](api.py) | **What a plugin imports.** The stable names for writing plugins, especially in other packages. | [docs/writing-plugins.md](../docs/writing-plugins.md) |

## The life of a run

From a click on **Run** (or a command, or a JSON file) to the files on disk:

```mermaid
flowchart TB
    run["A Run<br/>Scenario + Solver + Output"]
    build["Check the parts, mesh the case<br/>2-D rectangle or 3-D box"]
    iterate["Iterate<br/>until the stopping rule"]
    post["Post-process<br/>threshold, checks, exports"]
    files[("Results<br/>images, run.json, files")]
    run --> build --> iterate --> post --> files
```

| Step | Where |
| :-- | :-- |
| A Run | [`toporia_core/framework/problem/run.py`](framework/problem/run.py) |
| Check the parts, mesh the case | [`toporia_core/engine/loop.py`](engine/loop.py), [`toporia_core/engine/pipeline.py`](engine/pipeline.py), [`toporia_core/framework/problem/mesh.py`](framework/problem/mesh.py) |
| Iterate | [`toporia_core/engine/loop.py`](engine/loop.py); what one evaluation does: [`toporia_core/framework/README.md`](framework/README.md#one-evaluation-the-chain-of-parts) |
| Post-process | [`toporia_core/engine/postprocess.py`](engine/postprocess.py), [`toporia_library/postprocessors/`](../toporia_library/postprocessors/README.md) |
| Results | [`toporia_core/engine/records.py`](engine/records.py) |

The method can also be a whole method that does its own iteration (the RBF level set),
and the updater can be an outside library running its own loop in a background thread
(SciPy's SLSQP). To the engine they all look the same.

## Extending it

| You want to add… | Write | Guide |
| :--- | :--- | :--- |
| an update rule, or wrap an optimiser library | an updater in `toporia_library/updaters/` | [docs/writing-plugins.md](../docs/writing-plugins.md) |
| a filter or fabrication rule | a filter in `toporia_library/filters/` | 〃 |
| a new kind of design variable (bars, splines, a network) | a representation in `toporia_library/representations/` | [toporia_library/representations/README.md](../toporia_library/representations/README.md) |
| a threshold, check or export of the finished design | a post-processor in `toporia_library/postprocessors/` | [toporia_library/postprocessors/README.md](../toporia_library/postprocessors/README.md) |
| a continuation rule (how a parameter changes during the run) | a schedule in `toporia_library/schedules/` | [toporia_library/schedules/README.md](../toporia_library/schedules/README.md) |
| a material law (density to stiffness) | an interpolation in `toporia_library/interpolations/` | [toporia_library/interpolations/README.md](../toporia_library/interpolations/README.md) |
| an objective or constraint | a response in `toporia_library/responses/` | 〃 |
| a new physics or element | a physics engine in `toporia_library/physics/` and a three-line model | 〃 |
| a benchmark | a preset in `toporia_library/problems/` | [toporia_library/problems/README.md](../toporia_library/problems/README.md) |
| any of these, without touching this repository | your own package with an entry point | [docs/writing-plugins.md](../docs/writing-plugins.md#packaging-outside-this-repository) |

Then `toporia check kind:name`, and mark it ✅ in the folder's README.

## How the code is written

- **Every file opens with what it is and how it connects** — a comment header naming the
  file, what it holds, a small diagram where the data flow is not obvious, and the paper
  it implements, if any.
- **Every class and standalone function has a docstring.** Implementations of an
  interface method (`initialize`, `update`, `forward`, `evaluate`, …) do not repeat it:
  the method is documented once, in `toporia_core/framework/parts/`.
- **Comments say why**, or what a non-obvious line does — not what the code already says.
- **Parameters are declared, not read from dictionaries by hand**: a `Param` next to the
  code that uses it, so the GUI, sweeps and validation follow automatically.
- **Results are pinned.** `tests/golden/` stores eight runs bit for bit, one of them 3-D; a change that moves
  them is either a bug or is said in its commit, with the baseline regenerated.
