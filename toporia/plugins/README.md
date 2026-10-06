# Toporia library — the plug-in catalogue

Everything in `toporia/plugins/` is a plug-in. `toporia/framework/` defines the contracts;
this folder holds the implementations, and each sub-folder has its own README listing
**what is implemented here, what exists as open-source code elsewhere, and what only
exists as a paper.**

Those lists are a map of the field, not a promise. They exist so that anyone opening this
repository can see at a glance where Toporia sits in topology optimisation as a whole, and
what the next honest step is.

## Status labels

Every entry in every table in this library carries exactly one of these:

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented in this repository. The table links the file. |
| 🔗 **Open code** | Not in Toporia. A public reference implementation exists — port it, or validate against it. A 🔗 entry with no link means the code ships with the paper as supplementary material; follow the reference. |
| 📄 **Paper only** | Not in Toporia, and no public implementation found. Would be written from the paper, with the citation in the module docstring. |

Nothing is ever labelled ✅ until it is registered, tested, and reachable from the GUI.

## Where things live

| Folder | Layer | ✅ In Toporia | 🔗 Open code | 📄 Paper only |
| :-- | :-- | --: | --: | --: |
| [`methods/`](methods/README.md) | How the design is described | 15 | 14 | 2 |
| [`filters/`](filters/README.md) | How it is smoothed, projected, made manufacturable | 6 | 1 | 15 |
| [`interpolations/`](interpolations/README.md) | How density becomes stiffness (the material law) | 2 | 0 | 4 |
| [`models/`](models/README.md) | What computes the physics and the gradients | 2 | 24 | 3 |
| [`physics/`](physics/README.md) | Element formulations and discretisation | 1 | 6 | 3 |
| [`responses/`](responses/README.md) | What is minimised or constrained | 3 | 4 | 14 |
| [`updaters/`](updaters/README.md) | How the design moves each iteration | 7 | 8 | 3 |
| [`problems/`](problems/README.md) | Benchmark problems and datasets | 8 | 6 | 2 |
| **Total** | | **44** | **63** | **46** |

The 15 selectable methods are the 14 `model+updater` pairings plus the one whole
method; those pairings are built from the 2 models and 7 updaters counted in their own
rows, so they are not 15 separate implementations.

## The six choices

A topology optimisation method is not one algorithm. It is six mostly independent choices,
and almost every paper in the field changes exactly one of them and holds the rest fixed:

```
design variables  ──filter──>  physical density  ──engine──>  state  ──response──>  objective
       ^                                                                                 │
       └──────────────── updater <──── gradients <──── adjoint / backprop ───────────────┘
                                                              │
                                        fabrication rules ────┘
```

Toporia separates all six so a comparison can change one and only one:

| Choice | Contract | Registry |
| :-- | :-- | :-- |
| Parameterisation | [`framework.parts.method.OptimizationMethod`](../framework/parts/method.py) | `METHODS` + any `model+updater` pair |
| Regularisation | [`framework.parts.filter.Filter`](../framework/parts/filter.py) | `FILTERS` |
| Material law | [`framework.parts.interpolation.Interpolation`](../framework/parts/interpolation.py) | `INTERPOLATIONS` |
| What is optimised | [`framework.parts.model.Model`](../framework/parts/model.py) | `MODELS` |
| Physics engine | [`framework.parts.physics.Physics`](../framework/parts/physics.py) | declared by a model |
| Response | [`framework.parts.response.Response`](../framework/parts/response.py) | `RESPONSES` |
| Updater | [`framework.parts.updater.Updater`](../framework/parts/updater.py) | `UPDATERS` |
| Problem | [`framework.problem.scenario.Scenario`](../framework/problem/scenario.py) | `problems/` |

Most methods are not written by hand. A method is named `"<model>+<updater>"` and built on
demand, so any physics works with any update rule and **a new combination costs nothing at
all** — see [`methods/__init__.py`](methods/__init__.py). A new *engine* is not a new model
either: implement [`framework.parts.physics.Physics`](../framework/parts/physics.py) and every response and
filter applies to it unchanged.

## Adding one

**The guide is [`docs/writing-plugins.md`](../../docs/writing-plugins.md)**: a worked
example of every plugin kind, each one run and checked by the test suite.

There is no decorator and no list to maintain: a class in the right package, subclassing
the right base, with a non-empty `name`, **is** registered
([`framework/registry.py`](../framework/registry.py)). Parameters are declared as
[`Param`](../framework/params.py) objects next to the code that uses them, and the GUI, the
sweeps and the config validation are all generated from those declarations.

### From another package

A plugin does not have to live in this repository. Put it in your own package, import
only from [`toporia.api`](../api.py), and declare it with a standard entry point in your
`pyproject.toml`:

```toml
[project.entry-points."toporia.updaters"]
my_optimisers = "my_package.optimisers"            # every plugin class in a module
my_slsqp      = "my_package.optimisers:MySLSQP"    # or a single class
```

After `pip install my_package` it appears in the GUI menus, the CLI (`toporia list` shows
where each plugin comes from) and the configs. The groups are `toporia.models`,
`toporia.updaters`, `toporia.filters`, `toporia.interpolations`, `toporia.responses` and
`toporia.methods`. A plugin
that fails to import is reported in the GUI's log and by `toporia list`, and every other
plugin still loads. A plugin that needs an optional package declares
`dependencies = ("package",)`: where the package is missing it is greyed out in the menus
with the install command, and a run asking for it stops at once with that command.

Then run the conformance test on it — `toporia check updater:my_updater` on the command
line, **Check Parts** in the GUI's mode menu, or `toporia.checks.conformance(MyClass)` in a
test. It checks the interface, every gradient against finite differences, the adjoint of a
filter, and, for an updater, a benchmark run on the MBB beam within 10 % of optimality
criteria. Nothing is ✅ until it passes.

When you add one, change its row's marker from 🔗 or 📄 to ✅ in the folder's README, link
the file, and update the counts in the table above. Every table row carries exactly one
marker, so what is implemented here is never ambiguous. A list that is not maintained is
worse than no list.

## Why the lists are worth keeping

No open-source package holds the problem, the mesh and the constraints fixed while
swapping the parameterisation, the filter and the updater. That comparison — not another
SIMP implementation — is what Toporia is for, and these lists are how the gaps in it stay
visible.
