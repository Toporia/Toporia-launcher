# Framework assessment after the four research batches

[Computation guide](core.html) · [Variable/update guide](optimization.html) · [Batch 4 evidence](batch-4.md) · [The hard tasks in detail](hard-tasks-assessment.md)

The current framework can accept more implementations of its existing numerical
parts without a general rewrite. The hard boundary is **one structured physical
density field feeding one model evaluation**, not the number of library entries
or help pages. A nested GUI can plan and explain more than the present engine
can execute; those are different milestones.

## What the current code already provides

```text
Scenario + Solver -> representation -> scalar density -> filter chain
                                                    -> opaque physics state
                                                    -> responses + derivatives
                                                    -> Evaluation -> updater
```

| Existing boundary | Evidence and adaptation point |
| :-- | :-- |
| Registry identity and parameters | `kind:name`, `Param`, defaults and dependency declarations already support a larger library. [Registry](../../toporia/framework/registry.py), [parameters](../../toporia/framework/params.py) |
| Representation Jacobian | Geometric variables, spline coefficients and neural weights already return to one element field. [Contract](../../toporia/framework/parts/representation.py), [assembled model](../../toporia/plugins/models/assembled.py) |
| Opaque state and feature requirements | A physics state can contain displacements, modes or temperatures; response compatibility is checked through features. [Physics](../../toporia/framework/parts/physics.py), [responses](../../toporia/framework/parts/response.py) |
| Generic optimizer input | Objective, material budget, ordinary constraints and gradients live in `Evaluation`. [Model contract](../../toporia/framework/parts/model.py) |
| External optimizer lifecycle | Free-variable mapping, cached evaluations, callbacks, stop/close and library verdicts are implemented. [Flat view](../../toporia/framework/optimisers/flat_view.py), [external loop](../../toporia/framework/optimisers/external_loop.py) |
| Shared-variable variants | Repeated evaluations can combine mean/worst objectives and constraints. This is not a general transfer network. [Variants](../../toporia/framework/parts/variants.py) |
| Research knowledge | Plain descriptions, rendered equations, reports, stable function IDs and contribution templates can feed the GUI library/help. [Description data](../../toporia/plugins/problems/_research.py), [contribution template](templates/research-note.md) |

The selectable `model:q4` encapsulates filters, material, physics and responses;
it is not an opaque indivisible algorithm. The module map distinguishes these
computational functions from registry, mesh, plotting and orchestration support.

## What the new evidence says

- Native and pyMOTO elastic/thermal assemblies can be compared without changing the core contracts. Vibration comparisons must use the same normalization reference as well as the same physical field.
- A coarse displacement model can pass its own derivative checks and still make an artificially stiff design. The multiresolution companion's fine-Q4 compliance was 3.4 times its coarse value until the model began refusing filters smaller than one analysis cell (now 0.986). Independent analysis belongs in the evidence contract.
- Eigenfrequency, buckling, signed mechanism output and thermal objectives have different units and signs. Future result cards must use response metadata rather than universally labeling values as compliance or “higher is better.”
- `local_stress` returns a penalty with mutable multipliers. It cannot be treated as an ordinary inequality merely because it is listed under constraints.
- Post-processing order matters: thresholding changes the interpretation seen by connectivity and exports. An exported file does not inherit the original field's feasibility.

These are concrete requirements for future integration, rather than reasons to
replace all existing numerical files.

## Effort for the harder remaining tasks

The following are **estimated hours of agent execution**, including inspection,
implementation and relevant checks. They are not developer person-hours, measured
benchmarks or a promise to run unattended for that duration. They assume sources
and dependencies are available and a single bounded reference example is chosen.
The second column isolates framework plumbing; the third includes the first
usable numerical path. Tasks overlap, so the rows should not be added blindly.

| Task | Framework plumbing | First bounded, validated path | Main uncertainty |
| :-- | --: | --: | :-- |
| More filters, material laws or scalar responses on existing features | 0–2 h | 2–6 h | Correct derivatives and an identifiable source example usually dominate |
| Another general-vector optimizer adapter | 1–3 h | 3–7 h | Dependency/platform support, accepted-step conventions and constraint scaling |
| Whole-method external-code bridge | 3–6 h | 6–12 h | Process cancellation, coordinate/load mapping, source/runtime provenance |
| One-way coupled physics on the same structured field | 3–6 h | 8–16 h | Transfer of loads/states and complete cross-physics adjoints |
| Damped harmonic or transient response | 2–5 h | 10–20 h | Complex/time states, checkpointing, consistent adjoints and benchmark recovery |
| Independent multi-material phase variables | 6–12 h | 14–26 h | Material axis, simplex constraints, phase-aware interpolation and pinning |
| Executable nested network of functions | 6–12 h | 12–24 h | Variable ownership, typed ports, gradient joins, caches and lifecycle; GUI presentation is separate |
| Unstructured mesh/real CAD analysis path | 12–24 h | 24–48 h | Mesh protocol, quadrature, supports, field transfer, spatial filters and geometric exports |
| GPU/autodiff backend through an existing structured problem | 4–8 h | 12–24 h | NumPy/device boundaries, sparse solver differentiation, memory and optional-package support |

Source-paper recovery or a difficult nonlinear/eigenvalue convergence issue can
extend these ranges substantially. The [integration backlog](../../toporia/plugins/TODO.md)
contains historically recorded dependency blockers; this batch does not recheck
or install every unimplemented external package. No algorithm or physics listed
in this table was added by the assessment.

## Contracts needed before executing nested functions

| Decision | Concrete requirement |
| :-- | :-- |
| Variable ownership | A variable belongs to one declared design space. Shared variables are shared deliberately, not duplicated when a block is copied. |
| Ports | Declare scalar/vector/tensor field, physical units, grid, location and forward meaning. “Compatible shape” alone is insufficient. |
| Transfers | Mesh interpolation, load conversion and filtering must supply their transpose/adjoint, with declared boundary conventions. |
| Branch joins | Shared-variable gradients sum over contributions; worst-case/weighted objectives state their scaling explicitly. |
| State/cache lifetime | Changing geometry, material, schedule or mesh invalidates the appropriate solves and derivatives. Immutable recipe data does not make mutable solver states reusable. |
| External methods | Initialize/advance/stop/close and report ownership need to survive cancellation and errors without leaving optimizer workers alive. |
| Evidence | Preserve intended source, actual variant, complete settings, final physical metrics, convergence and reproduction statuses independently. |

For coupled residuals and a scalar objective, the necessary mathematical contract
is the complete coupled adjoint:

$$
R(u,z)=0,\quad (\partial_u R)^{\mathsf{T}}a=\partial_u J,\quad \nabla_zJ=\partial_zJ-(\partial_zR)^{\mathsf{T}}a
$$

Here u collects every coupled state, z the owned variables and a the adjoint.
Two independent sensitivity arrays cannot be joined safely if a transferred
state also changes another model's residual.

## Recommended next integration boundary

The GUI effort can first represent nested containment, link each function to
the delivered descriptions and show explicit port/compatibility placeholders.
Current numerical functions can remain adapted through their existing contracts.
Execution should start with one shared-variable, same-grid example and a complete
gradient check before introducing independent grids, transient states or new
material axes. The current `VariantModel` is a useful reference for shared
variables and aggregate responses, not a substitute for those new contracts.

Keep GUI and research work on separate workstream branches/checkouts, using batch
commits as the review units. Merge reviewed changes into the integration branch;
create a release tag such as `v0.2.2` only after the combined version is validated.
One version label should describe the combined release, rather than making two
workers edit the same version file. This batch creates no release tag and does
not modify the colleague's GUI checkout.
