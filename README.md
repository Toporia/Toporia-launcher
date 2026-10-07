# Toporia-launcher

A platform for topology-optimisation research: a robust framework in which algorithms,
filters and other approaches from the literature can be implemented, compared fairly and
brought to the world. Every choice in a method is a swappable part, so two runs that
differ in one part are a fair comparison.

## Getting started

```bash
pip install -e ".[dev,3d]"
```

Then `toporia` opens the desktop app, and `toporia run "MBB Beam"` runs from the command
line.

| You want to… | Read |
| :-- | :-- |
| change or extend Toporia, starting today | [docs/quickstart.md](docs/quickstart.md) |
| understand how the code fits together | [toporia/README.md](toporia/README.md) |
| add any kind of part, with a worked example of each | [docs/writing-plugins.md](docs/writing-plugins.md) |
| see what exists in the field, and what is here | [toporia/plugins/README.md](toporia/plugins/README.md) |

## What is implemented, and what is not

Every folder in [`toporia/plugins/`](toporia/plugins/README.md) carries a README that lists
its part of the field with one of three markers on **every single row**, so there is never
any doubt about what this repository actually does today:

| Marker | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here, registered and tested. The table links the file. |
| 🔗 **Open code** | Not here. A public reference implementation exists — port it, or validate against it. |
| 📄 **Paper only** | Not here, and no public code found. Would be written from the paper, with the citation in the module docstring. |

### Status at a glance

| Layer | ✅ In Toporia | 🔗 Open code | 📄 Paper only |
| :-- | :-- | --: | --: |
| [Methods](toporia/plugins/methods/README.md) — how the design is described | SIMP density, RBF level set, BESO | 12 | 3 |
| [Filters](toporia/plugins/filters/README.md) — regularisation and fabrication | density, sensitivity, Heaviside, AM overhang, symmetry, routing | 1 | 15 |
| [Design representations](toporia/plugins/representations/README.md) — what the variables are | element densities, moving morphable components | 2 | 3 |
| [Material laws](toporia/plugins/interpolations/README.md) — density to stiffness | SIMP, RAMP | 0 | 4 |
| [Schedules](toporia/plugins/schedules/README.md) — continuation, and robust variants | equal steps, geometric, linear ramp | 0 | 2 |
| [Post-processors](toporia/plugins/postprocessors/README.md) — threshold, checks, exports | threshold, connectivity, feature size, SVG, DXF, STL | 0 | 3 |
| [Models](toporia/plugins/models/README.md) — physics and gradients | 2-D Q4, 3-D H8, pyMOTO elasticity | 24 | 3 |
| [Elements](toporia/plugins/physics/README.md) — discretisation | Q4 plane stress, H8 solid | 5 | 3 |
| [Responses](toporia/plugins/responses/README.md) — objectives and constraints | compliance, volume, von Mises stress | 4 | 14 |
| [Updaters](toporia/plugins/updaters/README.md) — optimisers | OC, MMA, GCMMA, SiMPL, BESO, SLSQP | 8 | 3 |
| [Problems](toporia/plugins/problems/README.md) — benchmarks | MBB, cantilever, 3-D cantilever, Michell cantilever, 3-point bending, bar, 3× drone arm | 6 | 2 |

**58 implemented · 62 with open code elsewhere · 54 from papers only.**

Short version of where this sits in the field: Toporia solves linear elasticity on
structured grids, in 2-D and in 3-D. It covers four of the field's parameterisation
families (density/SIMP, parameterised level set, discrete evolutionary, moving morphable
components) with seven optimisers, plus continuation, robust design and post-processing.
The lists above are the honest map of everything it does not cover yet.

### The idea

A topology optimisation method is not one algorithm. It is a handful of mostly
independent choices: how the design is described, how it is filtered, what physics is
solved, how density becomes stiffness, what is measured, how the design is updated, how
parameters change during the run, and what is made of the result. Toporia separates them
all, so a comparison can change one and only one of them.

That is the gap worth filling: **no open-source package holds the problem, the mesh and the
constraints fixed while swapping the parameterisation, the filter and the updater.** Start
at [`toporia/plugins/README.md`](toporia/plugins/README.md).

### How the code fits together

[`toporia/README.md`](toporia/README.md) maps the package: its layers and the life of a
run, with diagrams. [`toporia/framework/`](toporia/framework/README.md),
[`toporia/engine/`](toporia/engine/README.md) and [`toporia/apps/`](toporia/apps/README.md)
each explain every file in them and how they interact.

### Adding to it

An algorithm, filter or response from a paper is one small file and one passing check, or
one installed package without touching this repository. Start with
[`docs/quickstart.md`](docs/quickstart.md); every kind of part, with a worked example, is in
[`docs/writing-plugins.md`](docs/writing-plugins.md).
