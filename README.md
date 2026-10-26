# Toporia

A platform for topology-optimisation research: a framework in which algorithms,
filters and other approaches from the literature can be implemented, compared fairly and
brought to the world. Every choice in a method is a swappable part, so two runs that
differ in one part are a fair comparison.

## Getting started

```bash
pip install -e ".[dev,3d]"
```

Then `toporia` opens the desktop app, and `toporia run "MBB Beam"` runs from the command
line.

## Comparing methods

Load a preset and choose **Compare Methods**. Compatible methods are selected for
that preset's physics and objective; the preset's recommended method is retained.
Other entries are disabled with an explanation on hover. You can change the
checked methods without changing the problem, mesh or stopping rule.

The study saves a design grid and `methods.csv` under `results/compare_methods/`.
It reports the objective, volume, stopping reason and constraint feasibility.
Mechanisms show signed output displacement, vibration shows fundamental frequency,
and thermal studies show thermal compliance. A method that completes a run has
not necessarily converged or met every constraint: check those columns.

Every bundled preset has a GUI-to-comparison regression test on a small mesh.
These short tests check setup and execution; method-specific tests check gradients
and physical benchmarks. Generated runs and test caches are disposable and are
not part of the source library.

| You want to… | Read |
| :-- | :-- |
| change or extend Toporia, starting today | [docs/quickstart.md](docs/quickstart.md) |
| understand how the code fits together | [toporia/README.md](toporia/README.md) |
| add any kind of part, with a worked example of each | [docs/writing-plugins.md](docs/writing-plugins.md) |
| see every code in the library, where it comes from, and what is still to add | [toporia/plugins/LIBRARY.md](toporia/plugins/LIBRARY.md) |
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
| [Whole methods](toporia/plugins/methods/README.md) | RBF, reaction-diffusion and Hamilton-Jacobi/topological-derivative level sets | 10 | 1 |
| [Filters](toporia/plugins/filters/README.md) — regularisation and fabrication | density, sensitivity, Heaviside (fixed or volume-preserving), PDE (isotropic or anisotropic), morphology, AM overhang, Gaynor–Guest support projection, symmetry, routing, extrusion, pattern, casting, Cartesian PDE machining | 1 | 5 |
| [Design representations](toporia/plugins/representations/README.md) — what the variables are | element densities, moving morphable components (constant or variable thickness), moving morphable voids (2D), capsule geometry projection (2D/3D), B-spline fields | 0 | 1 |
| [Material laws](toporia/plugins/interpolations/README.md) — density to stiffness | SIMP, RAMP, ordered SIMP | 0 | 3 |
| [Schedules](toporia/plugins/schedules/README.md) — continuation, and robust variants | equal steps, geometric, linear ramp, when the design settles | 0 | 1 |
| [Post-processors](toporia/plugins/postprocessors/README.md) — threshold, checks, exports | threshold, connectivity, feature size, grey level over the run, SVG, DXF, STL, smoothed outlines | 0 | 1 |
| [Models](toporia/plugins/models/README.md) — physics and gradients | 2-D Q4, 3-D H8, pyMOTO elasticity; heat (2-D, 3-D, pyMOTO); vibration (Q4, pyMOTO); large deformation; linearised buckling; port springs and compliant mechanisms | 24 | 3 |
| [Elements](toporia/plugins/physics/README.md) — discretisation | Q4 plane stress, H8 solid, Q4 and H8 heat, Q4 with mass, Q4 large deformation, Q4 buckling, Q4 with port springs | 5 | 3 |
| [Responses](toporia/plugins/responses/README.md) — objectives and constraints | compliance, phase-field energy, geometric minimum length, volume, von Mises stress (peak and local), thermal compliance, end compliance, eigenfrequency, dynamic compliance, buckling load factor, signed output displacement | 4 | 12 |
| [Updaters](toporia/plugins/updaters/README.md) — optimisers | OC, MMA, GCMMA, SiMPL, BESO, SLSQP, trust-constr, NLopt (MMA, CCSAQ, SLSQP, AUGLAG), mmapy (MMA, GCMMA), null-space, TOBS, CONLIN, multi-constraint OC, Adam, PTO, hard-kill BESO, augmented Lagrangian, floating projection | 4 | 0 |
| [Problems](toporia/plugins/problems/README.md) — benchmarks | MBB, robust MBB, cantilever, 3-D cantilever, Michell cantilever, L-bracket, L-bracket (local stress), heat sink, vibrating beam, column buckling, non-linear cantilever, force inverter, 3-point bending, bar, 3× drone arm | 6 | 0 |

**109 implementations: 84 selectable plugins, 8 physics engines and 17 presets.
54 catalogue entries have open code elsewhere; 30 are paper-only.**
Plugin counts follow the registries; composed pairings and parameter options are
not counted again as additional implementations.

Toporia solves structural elasticity and steady heat conduction on structured
2-D and 3-D grids, with additional 2-D vibration, harmonic response, large deformation
and linearised buckling. It covers density/SIMP, parameterised level set,
discrete evolutionary and moving morphable component designs, with 23 updaters,
continuation, robust design and post-processing.
The lists above are the honest map of everything it does not cover yet.

### The idea

A topology optimisation method is not one algorithm. It is a handful of mostly
independent choices: how the design is described, how it is filtered, what physics is
solved, how density becomes stiffness, what is measured, how the design is updated, how
parameters change during the run, and what is made of the result. Toporia separates them
all, so a comparison can change one and only one of them.

Toporia keeps the problem, mesh and constraints fixed while comparing compatible
parameterisations, filters and updaters. Start at
[`toporia/plugins/README.md`](toporia/plugins/README.md).

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
