# Adding computational functions

GUI function authoring is future work. Current functions are ordinary Python
plugins discovered by the existing registries, and nested composition is saved
as a validated data-only workflow.

## Plugin contracts

Choose the existing contract in `toporia/framework/parts/`: representation,
filter, model, updater, response, interpolation, schedule, method, or postprocess.
A whole method implements optimization lifecycle itself; an assembled method
combines a model (physics, responses, gradients) and an updater (design changes).
Do not register a new numerical model as a display-only network node.

Subclass the appropriate base, implement its abstract methods and declare a
unique nonempty `name`, readable `label`, docstring, `reference`, parameters and
supported dimensions/capabilities. Optional packages belong in `dependencies`.
Parameter declarations drive validation, generated controls and sourced help.
State units, ranges, defaults, input/output meaning and any approximations.

For example, a filter implements `forward(x)` and
`backward(x_in, sensitivity)`; `setup(problem, solver)` prepares its mesh-dependent
state. Set `exact_adjoint` accurately and implement `backward_volume` separately
only when its volume derivative differs. See `plugins/filters/density.py` and
`framework/parts/filter.py` for the existing contracts and examples.

## Discovery and validation

Built-in registries scan non-underscore modules under their plugin package.
Adding a subclass in `toporia/plugins/filters/`, for example, makes it available
without editing a central list. External packages can declare an entry point,
such as `[project.entry-points."toporia.filters"]`, pointing to a plugin module
or class. Registries also support explicit `register()` for scripts/tests.

Run the relevant conformance checks, including finite-difference derivative
checks where applicable, plus a small numerical example. Do not regenerate
golden baselines to hide a numerical behavior change. Add meaningful tests for
new capabilities and dependency/compatibility failures.

The Function Explorer reads all installed registries automatically. Its placement
map distinguishes numerical functions from operating-space, project, composition
and export infrastructure. The local filter library filters entries by dimension.
New integration-branch functions should be brought into this checkout through
the separately planned integration work; this GUI change does not merge branches.

## Nested execution

`framework/problem/workflow.py` defines the portable tree: optimization leaves,
sequential containers and parallel containers. IDs are unique safe names;
unknown kinds, malformed children and unsupported depth/size are rejected.
Each optimization records solver settings and allowed scenario overrides.
All stages share the physical domain and mesh resolution. Export is a mandatory
terminal function in the UI; it writes the selected completed result.

`engine/workflow.py` executes that contract. Sequential restriction is implemented
as actual per-element void bounds and a budget relative to the allowed volume.
Parallel functions share inputs and combine completed designs; scheduling is
consecutive, not a coupled or simultaneous solve. Compatibility must be enforced
both in GUI preflight and in the headless executor. Do not add executable edges
without defining their data contract, transformation and persistence behavior.

The knowledge base currently uses plugin documentation and references. Researcher
contributions should improve those sources; a collaborative annotation/editor
system has not been implemented.
