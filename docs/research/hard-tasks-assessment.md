# The hard tasks: what each needs, how much work, what stays compatible

29 October 2026. A follow-up to the [framework assessment](framework-assessment.md),
which listed six tasks as needing more than a new plugin. This note reads the
code for each and answers three questions: what actually has to change, roughly
how much work it is, and whether the current functions keep working unchanged.

Effort is in **hours of agent work** (implementation, tests, one validated
showcase), as in the earlier table. It is a planning range, not a measurement.

## Where the code is general already, and where it is not

| Layer | Assumes one scalar field on a structured grid? |
| :-- | :-- |
| Engine loop, schedules, stopping rule (`engine/loop.py`) | **No.** It sees an `OptimizationMethod` and a density array; only the result images and CSV expect a 2-D or 3-D grid. |
| `Model`, `Evaluation`, `Updater` (`framework/parts`) | **No.** A design may have any shape; all 19 updaters work element-wise or on the flat view, and none reads the mesh. |
| `ComposedMethod`, `VariantModel` | **No.** Both combine models through `evaluate()` alone. |
| `Representation` | Partly. It returns *one* element field; 5 of 6 representations use grid coordinates. |
| Filters | Partly. 7 of 16 use grid offsets (`neighbour_matrix`, PDE stencils, the fabrication filters' build direction). |
| `Physics` | **Yes.** Fields have the density's shape; 9 of 10 engines assemble Q4/H8 on the grid. |
| `BaseProblem` (`framework/problem/mesh.py`) | **Yes.** It promises `nelx`, `nely`, node masks of shape `(nely+1, nelx+1)`. |
| Interpolations (5) and most responses (10 of 12) | **No.** They read only the density and the physics' answers. |

The core loop and the optimiser side are already general. The grid assumption
lives in four places: the problem, the physics engines, the grid-based filters
and representations, and the plotting.

## The six tasks

### 1. Several materials, each with its own design variables

**What changes.** The material axis enters in the model layer, not the core. A
representation returns `(M, *shape)` instead of `shape`; a multi-phase
interpolation (DMO or a phase-aware SIMP) reduces it to one stiffness per element,
so the existing isotropic Q4/H8 engines solve unchanged. Needed:
- the representation and interpolation for M phases, with their Jacobians;
- the filter chain applied per phase (most filters work on the last axes already);
- one volume budget per phase: `Evaluation` has one `volume`, so the others go in
  as ordinary constraints (MMA, GCMMA, SLSQP and multi-constraint OC take them; plain OC does not);
- result images in colour per phase, and post-processors that pick a phase.

Anisotropic phases (different material tensors) would need the physics too.

**Effort.** 12–20 h for isotropic phases; another 10–20 h for anisotropic ones.

**Compatible?** Yes, if `M = 1` stays the default: today's fields are then the
single-phase case and every current function sees the shape it sees now.
`ordered_simp` (one variable, several material levels) stays as it is.

### 2. An executable network of nested functions

**What changes.** Less than the earlier assessment feared. `VariantModel`
already shows the pattern: a `Model` built from other models, joined through
`evaluate()`. A network becomes one new model plugin:
- typed ports (field shape, units, grid);
- a topological order and caching per node;
- gradient joins (sums for a shared variable, chain rule for a chain);
- transfers that carry their adjoint.

The engine, the updaters and the method interface stay as they are; the engine
still sees one model. The GUI's network view describes this model.

**Effort.** 10–18 h for same-grid nodes with a full gradient check; +8–15 h for
transfers between different grids.

**Compatible?** Yes. Existing models become single nodes; nothing is rewritten.

### 3. Unstructured meshes and real CAD geometry

**What changes.** This one is a real rewrite of the grid layer, though not of the
optimiser side:
- `BaseProblem` gains a mesh protocol: element centroids, volumes, connectivity,
  boundary sets by name. `RectangularProblem` and `BoxProblem` implement it on
  top of what they have now;
- new physics engines (triangles or tetrahedra, or a bridge to an external FE
  code, pyMOTO or FEniCS);
- a distance-based density filter (a sparse neighbour search instead of grid
  offsets); PDE filters need an FE Laplacian on that mesh;
- plotting via triangulated patches instead of `imshow`; STL/DXF from the mesh.

The fabrication filters (AM, casting, extrusion, machining) use a grid build
direction and would stay grid-only. So would the B-spline and MMC
representations, unless rewritten.

**Effort.** 30–60 h for a first 2-D triangle path with filter, compliance,
export and a validated example; 3-D and CAD import roughly double it.

**Compatible?** Yes, provided the mesh protocol is added beside the grid
attributes and nothing is removed. Every grid plugin then declares that it needs
a structured problem, and the preflight refuses it on an unstructured one, as it
already refuses wrong dimensions. Nothing existing changes behaviour.

### 4. A GPU or automatic-differentiation backend

**What changes.** Mostly plugins. The `Physics` interface hands opaque states
between its own methods, so a JAX or PyTorch engine can keep its arrays on the
device and return NumPy only at the response boundary. Needed:
- a sparse or matrix-free solver on the device;
- the adjoint, from autodiff or written out;
- an optional dependency.

Whole-pipeline autodiff (filters, interpolation, physics in one graph) would
replace the hand-written chain rule for that pipeline only, as the pyMOTO models
already do with their own network.

**Effort.** 12–24 h for one engine with a gradient check against Q4; a fully
differentiable pipeline 25–40 h.

**Compatible?** Yes. It is a new model or engine beside the others; the core is
unchanged.

### 5. Two coupled physics (thermo-elastic, fluid-structure)

**What changes.** One-way coupling on the same grid, such as thermal expansion
loads from a temperature field, fits one physics plugin that provides both
features and does the coupled adjoint inside. Its responses stay as they are. Two-way or
cross-grid coupling needs the coupled-adjoint contract of the framework
assessment, `R(u, z) = 0` with one adjoint over all states. That belongs in the
network model of task 2 rather than in the core.

**Effort.** 8–16 h one-way thermo-elastic; 20–40 h two-way, after task 2.

**Compatible?** Yes. Single-physics engines are untouched.

### 6. Damped harmonic and transient responses

**What changes.** Inside physics plugins:
- complex states for damped harmonic response;
- time stepping with a stored or checkpointed history and a backward adjoint for
  transient response.

`Physics`, `Response` and the engine need nothing new, since the state is
opaque. The run report needs response metadata, because these values are not
"compliance".

**Effort.** 10–20 h damped harmonic; 20–35 h transient with checkpointing.

**Compatible?** Yes.

## Summary

| Task | Touches the core? | Agent hours | Current functions |
| :-- | :-- | --: | :-- |
| Several materials (isotropic) | Representation/interpolation shape, per-phase budgets | 12–20 | Unchanged (M = 1 default) |
| Network of functions | No: one new model plugin | 10–18 (+8–15 cross-grid) | Unchanged |
| Unstructured mesh / CAD | Problem protocol, filters, plotting | 30–60 (2-D) | Unchanged; grid-only parts refused on other meshes |
| GPU / autodiff | No: new engine or model | 12–24 (25–40 whole pipeline) | Unchanged |
| Coupled physics | One-way: no; two-way: via the network | 8–16 / 20–40 | Unchanged |
| Damped harmonic / transient | No: physics plugins | 10–20 / 20–35 | Unchanged |

No task needs the existing functions rewritten or their results changed. Only
the unstructured mesh needs real core work: a mesh protocol next to the grid.
The others come down to a new model, engine or representation, plus some
reporting. The order that saves the most work:

1. The network model (task 2). Coupled physics and cross-grid work build on it.
2. Then the mesh protocol (task 3), before the folder split, so `toporia_core`
   is cut along an interface that already allows non-grid problems.
