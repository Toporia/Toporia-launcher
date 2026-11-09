# Toporia

A platform for topology-optimisation research: a framework in which algorithms,
filters and other approaches from the literature can be implemented, compared fairly and
brought to the world. Every choice in a method is a swappable part, so two runs that
differ in one part are a fair comparison.

*Version 0.3.0.*

## Getting started

**On Windows, without Python:** unzip `Toporia-0.3.0-windows.zip` and start
`Toporia\Toporia.exe`. (Windows may say the publisher is unknown: the program is not
code-signed. Choose *More info → Run anyway*.)

**From the sources, on any system:**

```bash
pip install -e ".[dev,3d,gui3d]"
```

This installs pyMOTO too. The GPL-3 optimisers are separate (see Licence):

```bash
pip install -e ".[mmapy]"
```

Then `toporia` opens the desktop app, and `toporia run "MBB Beam"` runs from the command
line. New to Python, or the install fails? [docs/installation.md](docs/installation.md)
walks through it step by step.

## Licence

Toporia is Apache-2.0. pyMOTO is installed with it and is in the Windows program; NLopt
is installed where a working build exists (not on Python 3.15, see the notices). Two optional optimisers, **mmapy** and **nullspace_optimizer**, are **GPL-3**, so
they are never installed by default and never bundled: a program that contains them has to
be distributed under GPL-3. [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) explains what
that means, and lists every package and its licence.

## The desktop app

Five steps along the top, always in reach: **Problem** (design space, loads, supports,
material in MPa with presets, physics, objective and constraints, the volume budget among
them), **Method** (the whole computation as one collapsible tree, with one *Add function*
button), **Runner** (one run, sweeps, comparisons; a run can show in its own window while
you keep working), **Post-process** (every run of a study, and its stress, displacement,
strain-energy or temperature field in colour) and **Export** (with a preview of what the
file holds). Home opens recent projects, the benchmark library, the function explorer
(each function with its showcase) and the documentation.

## Comparing methods

Load a preset and choose **Compare Methods**. Choose the physics once; the list then holds
its updaters and the whole methods. Compatible methods are selected for that preset's
physics and objective; the preset's recommended method is retained. Other entries are
disabled with an explanation on hover. You can change the checked methods without changing
the problem, mesh or stopping rule.

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
| install it, step by step, with fixes for common problems | [docs/installation.md](docs/installation.md) |
| change or extend Toporia, starting today | [docs/quickstart.md](docs/quickstart.md) |
| understand how the code fits together | [toporia_core/README.md](toporia_core/README.md) |
| add any kind of part, with a worked example of each | [docs/writing-plugins.md](docs/writing-plugins.md) |
| see every code in the library, where it comes from, and what is still to add | [toporia_library/LIBRARY.md](toporia_library/LIBRARY.md) |
| explore the research's geographic and historical origins, with a map, timeline and source data | [docs/research-origins/README.md](docs/research-origins/README.md) |
| see what exists in the field, and what is here | [toporia_library/README.md](toporia_library/README.md) |

## What is implemented, and what is not

Every folder in [`toporia_library/`](toporia_library/README.md) carries a README that lists
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
| [Whole methods](toporia_library/methods/README.md) | RBF, reaction-diffusion and Hamilton-Jacobi/topological-derivative level sets; ground-structure truss (2-D/3-D), kept as bars, with Toporia's own joint and anchored nodes; density on unstructured meshes (triangles in 2-D, tetrahedra fitted to curved voids in 3-D) | 10 | 1 |
| [Filters](toporia_library/filters/README.md) — regularisation and fabrication | density, sensitivity, Heaviside (fixed or volume-preserving), PDE (isotropic or anisotropic), morphology, AM overhang, Gaynor–Guest support projection, symmetry, routing, extrusion, pattern, casting, Cartesian PDE machining | 1 | 4 |
| [Design representations](toporia_library/representations/README.md) — what the variables are | element densities, density and material choice (multi-material), density and fibre angle, moving morphable components (constant or variable thickness), moving morphable voids (2D), capsule geometry projection (2D/3D), B-spline fields, NumPy neural coordinate fields (2D/3D) | 0 | 0 |
| [Material laws](toporia_library/interpolations/README.md) — stiffness and resource cost | SIMP, RAMP, multi-material DMO, ordered SIMP, basic SINH (shared-density variant), Hashin-Shtrikman fixed-nu upper envelope | 0 | 1 |
| [Schedules](toporia_library/schedules/README.md) — continuation, and robust variants | equal steps, geometric, linear ramp, when the design settles | 0 | 1 |
| [Post-processors](toporia_library/postprocessors/README.md) — threshold, checks, exports | threshold, connectivity, feature size, grey level over the run, SVG, DXF, STL, smoothed outlines, truss to a clean solid, the fitted boundary of an unstructured mesh | 0 | 1 |
| [Models](toporia_library/models/README.md) — physics and gradients | 2-D Q4, fibre-reinforced Q4 (angle per element), nested multiresolution Q4, 3-D H8, pyMOTO elasticity; heat (2-D, 3-D, pyMOTO); vibration (Q4, pyMOTO); large deformation; linearised buckling; port springs and compliant mechanisms | 24 | 3 |
| [Elements](toporia_library/physics/README.md) — discretisation | Q4 plane stress, Q4 orthotropic lamina, nested multiresolution Q4, H8 solid, Q4 and H8 heat, Q4 with mass, Q4 large deformation, Q4 buckling, Q4 with port springs | 5 | 3 |
| [Responses](toporia_library/responses/README.md) — objectives and constraints | compliance, phase-field energy, geometric minimum length, volume, von Mises stress (peak and local, as constraint or objective), combined objectives (weighted sum, min-max, formula), your own variables, thermal compliance, end compliance, eigenfrequency, dynamic compliance, buckling load factor, signed output displacement | 4 | 12 |
| [Updaters](toporia_library/updaters/README.md) — optimisers | OC, MMA, GCMMA, SiMPL, BESO, SLSQP, trust-constr, NLopt (MMA, CCSAQ, SLSQP, AUGLAG), mmapy (MMA, GCMMA), null-space, TOBS, CONLIN, multi-constraint OC, Adam, PTO, hard-kill BESO, augmented Lagrangian, floating projection | 4 | 0 |
| [Problems](toporia_library/problems/README.md) — benchmarks | MBB, robust MBB, cantilever, 3-D cantilever, Michell cantilever, L-bracket, L-bracket (local stress), heat sink, vibrating beam, column buckling, non-linear cantilever, force inverter, 3-point bending, bar | 6 | 0 |

**211 implementations: 100 selectable plugins, 10 physics engines and 101 presets.
54 catalogue entries have open code elsewhere; 26 are paper-only.**
Plugin counts follow the registries; composed pairings and parameter options are
not counted again as additional implementations.

Toporia solves structural elasticity and steady heat conduction on structured
2-D and 3-D grids, with additional 2-D vibration, harmonic response, large deformation
and linearised buckling. It covers density/SIMP, parameterised level set,
discrete evolutionary and moving morphable component designs, with 24 updaters,
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
[`toporia_library/README.md`](toporia_library/README.md).

### How the code fits together

[`toporia_core/README.md`](toporia_core/README.md) maps the package: its layers and the life of a
run, with diagrams. [`toporia_core/framework/`](toporia_core/framework/README.md),
[`toporia_core/engine/`](toporia_core/engine/README.md) and [`toporia_gui/`](toporia_gui/README.md)
each explain every file in them and how they interact.

### Adding to it

An algorithm, filter or response from a paper is one small file and one passing check, or
one installed package without touching this repository. Start with
[`docs/quickstart.md`](docs/quickstart.md); every kind of part, with a worked example, is in
[`docs/writing-plugins.md`](docs/writing-plugins.md).

### Research figures and mathematical explanations

The [research guide](docs/research/README.md) maps numerical functions to paper
targets, explains the core computation with diagrams and rendered equations, and
tracks reproduction evidence separately from pending work. The first two
research presets target Andreassen et al. Figure 3(a); their preset **?** opens
the setup and mathematical description. See the [Batch 1 report](docs/research/batch-1.md)
for author-code comparisons, paper-review scope and rerun commands.

[Batch 2](docs/research/batch-2.md) adds filter, material-law and continuation
figures with mathematical descriptions. Its [gallery](docs/research/evidence/batch2/index.html)
separates matched research curves from unresolved demonstrations. A failed
volume-preserving-projection companion is quarantined in the to-fix queue.

[Batch 3](docs/research/batch-3.md) adds 31 optimizer, representation and level-set
companions with mathematical help. Its [gallery](docs/research/evidence/batch3/index.html)
records bounded runs and independent checks; full paper reproductions remain
unresolved. The [optimization guide](docs/research/optimization.html) explains
design-variable gradients, updater interfaces and final-result checks.

[Batch 4](docs/research/batch-4.md) covers the remaining physics, responses and
post-processing functions with 19 further companions and 25 demonstrations.
The [framework assessment](docs/research/framework-assessment.html) separates
existing extension points from the work needed for coupled states, nested
execution, material phases and unstructured meshes. Complete example coverage
does not mean that every source-paper figure has been reproduced.
