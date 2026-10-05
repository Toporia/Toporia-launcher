# Toporia-launcher
This repository is meant to be a platform for all topological optimization research. It is a robust framework where algorithms, filter and other approaches can be implemented, compaired and brought to the world.

## What is implemented, and what is not

Every folder in [`toporia/library/`](toporia/library/README.md) carries a README that lists
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
| [Methods](toporia/library/methods/README.md) — how the design is described | SIMP density, RBF level set, BESO | 14 | 3 |
| [Filters](toporia/library/filters/README.md) — regularisation and fabrication | density, sensitivity, Heaviside, AM overhang, symmetry, routing | 1 | 15 |
| [Models](toporia/library/models/README.md) — physics and gradients | 2-D Q4, pyMOTO elasticity | 24 | 3 |
| [Elements](toporia/library/fe/README.md) — discretisation | Q4 plane stress | 6 | 3 |
| [Responses](toporia/library/responses/README.md) — objectives and constraints | compliance, volume, von Mises stress | 4 | 14 |
| [Updaters](toporia/library/updaters/README.md) — optimisers | OC, MMA, GCMMA, SiMPL, BESO | 9 | 3 |
| [Problems](toporia/library/problems/README.md) — benchmarks | MBB, cantilever, 3-point bending, bar, 3× drone arm | 6 | 3 |

**38 implemented · 64 with open code elsewhere · 44 from papers only.**

Short version of where this sits in the field: Toporia is 2-D, structured-grid, linear
elastic today, and it covers three of the field's parameterisation families (density/SIMP,
parameterised level set, discrete evolutionary) with six optimisers. The lists above are
the honest map of everything it does not cover yet.

### The idea

A topology optimisation method is not one algorithm — it is six mostly independent choices:
how the design is described, how it is filtered, what physics is solved, what response is
measured, how the design is updated, and what can be manufactured. Toporia separates all
six so a comparison can change one and only one of them.

That is the gap worth filling: **no open-source package holds the problem, the mesh and the
constraints fixed while swapping the parameterisation, the filter and the updater.** Start
at [`toporia/library/README.md`](toporia/library/README.md).
