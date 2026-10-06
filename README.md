# Toporia-launcher
This repository is meant to be a platform for all topological optimization research. It is a robust framework where algorithms, filter and other approaches can be implemented, compaired and brought to the world.

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

Short version of where this sits in the field: Toporia is 2-D, structured-grid, linear
elastic today, and it covers three of the field's parameterisation families (density/SIMP,
parameterised level set, discrete evolutionary) with seven optimisers. The lists above are
the honest map of everything it does not cover yet.

### The idea

A topology optimisation method is not one algorithm — it is six mostly independent choices:
how the design is described, how it is filtered, what physics is solved, what response is
measured, how the design is updated, and what can be manufactured. Toporia separates all
six so a comparison can change one and only one of them.

That is the gap worth filling: **no open-source package holds the problem, the mesh and the
constraints fixed while swapping the parameterisation, the filter and the updater.** Start
at [`toporia/plugins/README.md`](toporia/plugins/README.md).

### How the code fits together

[`toporia/README.md`](toporia/README.md) maps the package — its layers and the life of a
run, with diagrams — and [`toporia/framework/`](toporia/framework/README.md) and
[`toporia/engine/`](toporia/engine/README.md) each explain every file in them and how
they interact.

### Adding to it

An algorithm, filter or response from a paper is one small file and one passing check —
or one installed package, without touching this repository. The guide, with a worked
example of every kind: [`docs/writing-plugins.md`](docs/writing-plugins.md).
