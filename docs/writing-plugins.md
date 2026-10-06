# Writing a plugin

Toporia is built so that an algorithm, a filter or a response from a paper is **one small
file and one passing check**. This guide shows how, kind by kind. Every code block marked
`# example:` is run by the test suite (`tests/checks/test_guide.py`), so what you read here works.

## The pieces

A topology-optimisation method is a chain of independent choices. Each is a plugin kind:

```
design variables z
   │  Representation   z → element densities
   │  Filter           → physical density ρ
   │  Physics          ρ → state (displacements, stresses)
   │  Response         → objective and constraints, with gradients
   ▼  Updater          → the next design variables, and round again

The gradients travel back up the same chain: each part carries the sensitivity
of the one below it back to its own input.
```

| You have…                                        | Write a…                 | Subclass                    | Folder / entry-point group       |
| :----------------------------------------------- | :----------------------- | :-------------------------- | :------------------------------- |
| an update rule (OC, MMA, BESO, a new idea)       | updater                  | `Updater`                   | `plugins/updaters/` · `toporia.updaters` |
| a library that runs its own loop (SciPy, NLopt)  | updater                  | `ExternalOptimizer`         | `plugins/updaters/` · `toporia.updaters` |
| a new kind of design variable (bars, splines)    | representation           | `Representation`            | `plugins/representations/` · `toporia.representations` |
| a smoothing, projection or fabrication rule      | filter                   | `Filter`                    | `plugins/filters/` · `toporia.filters` |
| a material law (density → stiffness)             | interpolation            | `Interpolation`             | `plugins/interpolations/` · `toporia.interpolations` |
| a continuation rule (a parameter over the run)   | schedule                 | `Schedule`                  | `plugins/schedules/` · `toporia.schedules` |
| a check or export of the finished design         | post-processor           | `PostProcessor`             | `plugins/postprocessors/` · `toporia.postprocessors` |
| an objective or constraint                       | response                 | `Response`                  | `plugins/responses/` · `toporia.responses` |
| a finite-element solver or other physics         | physics engine + model   | `Physics`, `AssembledModel` | `plugins/physics/`, `plugins/models/` · `toporia.models` |
| a method that does not split into the above      | whole method             | `OptimizationMethod`        | `plugins/methods/` · `toporia.methods` |

Every piece works with every other: an updater never sees the physics, a response never
sees the updater. A run names its method as `"<model>+<updater>"`, e.g. `"q4+mma"`, so a
new updater is immediately usable with every model, and a new response or filter with
every updater.

Import everything from **`toporia.api`** — it is the stable surface; the internal modules
may move.

## Five steps

1. **Write the class** in the right folder (or in your own package — see *Packaging*).
   Give it a `name` (the registry key), a `label` (for menus) and its `params`.
2. **There is no step 2.** A class with a `name` in the right package *is* registered: it
   appears in the GUI menus, in `toporia list`, and in configs.
3. **Check it:** `toporia check updater:my_updater` (or **Check Parts** in the GUI's mode
   menu, or `conformance(MyUpdater).assert_ok()` in a test). It checks the interface,
   every gradient against finite differences, and — for an updater — a benchmark against
   optimality criteria. Fix what it reports.
4. **Run it** from the GUI: pick it as the updater (or filter, objective, …); the
   **Pipeline** panel shows where it sits in the chain.
5. **Mark it ✅** in the folder's README, with the paper's citation in the module docstring.

## Parameters

Declare every tunable value as a `Param`. The GUI form, the sweep menus, config
validation and the defaults all come from these declarations:

```python
Param("step", 0.1, "Step size", "Largest change of a variable per iteration.",
      min=0.001, max=1.0, step=0.01, decimals=3)
```

Your code receives the resolved values as a dict (`settings["step"]`). Parameter names
must be unique within a method — a model's and an updater's are combined.

## An updater: your own update rule

An updater receives the current design `x` (shaped like the model's design, usually
`(nely, nelx)`) and its `Evaluation`, and returns the next design:

| `evaluation.`        | what it is                                                             |
| :------------------- | :--------------------------------------------------------------------- |
| `objective`          | the value being minimised                                              |
| `objective_gradient` | its gradient, shaped like `x`                                          |
| `volume`, `volume_gradient` | total physical material and its gradient; the budget is `model.volume_limit` |
| `constraints`        | the scenario's further constraints, each with `.value` (≤ 0 satisfied) and `.gradient` |

`model.bounds()` gives per-variable bounds (holes and solid rings have equal bounds), and
`model.volume_of(x)` gives a design's material without a solve — cheap enough to call in a
bisection. A projected-gradient update with a bisection on the volume multiplier:

```python
# example: updater
import numpy as np

from toporia.api import Param, Updater


class ProjectedGradient(Updater):
    """Steepest descent with a move limit, the volume budget met by bisection."""

    name = "guide_projected_gradient"
    label = "Projected gradient (guide example)"
    params = (Param("pg_move", 0.1, "Move limit", "Largest change of a density per step.",
                    min=0.01, max=1.0, step=0.01, decimals=2),)
    objectives = ("compliance",)   # tested on compliance only
    max_constraints = 0            # the volume budget, nothing more

    def initialize(self, model, settings):
        self.model, self.move = model, settings["pg_move"]
        self.lower, self.upper = model.bounds()

    def update(self, x, evaluation, completed):
        scale = np.max(np.abs(evaluation.objective_gradient)) or 1.0
        direction = -evaluation.objective_gradient / scale
        volume = evaluation.volume_gradient / (np.max(np.abs(evaluation.volume_gradient)) or 1.0)

        def design(multiplier):
            step = np.clip(direction - multiplier * volume, -self.move, self.move)
            return np.clip(x + step, self.lower, self.upper)

        low, high = 0.0, 1e3
        for _ in range(80):        # the volume falls as the multiplier rises
            middle = 0.5 * (low + high)
            if self.model.volume_of(design(middle)) > self.model.volume_limit:
                low = middle
            else:
                high = middle
        return design(high)
```

Declare honestly what it can do: `objectives` (which responses it may minimise; `None`
means any) and `max_constraints` (how many constraints besides the volume budget; `None`
means any number). The GUI only offers what the pairing can do, and explains the rest.

## An updater: a library that runs its own loop

SciPy, NLopt, IPOPT and most published optimisers want callbacks and run until they are
done. Subclass `ExternalOptimizer` and write one method, `run(flat, x0, iterate)`:

* `flat` is the problem as such libraries expect it (below);
* call `iterate(x)` wherever the library reports a new design — its callback;
* return a `Verdict` with the library's own success flag and message.

Toporia runs your `run` in a background thread and takes one design per `iterate`, so the
live display, the stopping rule and the Stop button work as for any other updater, and
the library's verdict is written to `run.json`. The complete SciPy SLSQP adapter,
[`plugins/updaters/scipy_slsqp.py`](../toporia/plugins/updaters/scipy_slsqp.py), is the
template:

```python
# example: external
import numpy as np
from scipy.optimize import Bounds, minimize

from toporia.api import ExternalOptimizer, Param, Verdict


class TrustConstr(ExternalOptimizer):
    """SciPy's trust-region interior point, through the same few lines as SLSQP."""

    name = "guide_trust_constr"
    label = "trust-constr (SciPy, guide example)"
    params = (Param("tc_maxiter", 100, "Iterations", "SciPy's iteration limit.", min=1, max=10000),)
    max_constraints = None          # it takes any number of constraints
    flat_objective_scale = 1.0      # start the objective at 1

    def run(self, flat, x0, iterate):
        result = minimize(
            flat.f, x0, jac=flat.df, method="trust-constr",
            bounds=Bounds(flat.lower, flat.upper),
            constraints=[{"type": "ineq", "fun": flat.g_geq, "jac": flat.dg_geq}],
            callback=lambda intermediate_result: iterate(intermediate_result.x),
            options={"maxiter": self.settings["tc_maxiter"]},
        )
        return Verdict(bool(result.success), str(result.message), np.asarray(result.x),
                       iterations=int(result.nit), evaluations=int(result.nfev))
```

Wrapping a library is that short; whether the library is any *good* at topology
optimisation is a separate question, and the conformance check answers it. Run on this
example, `toporia check` passes every interface check but fails the benchmark:
trust-constr ends far above optimality criteria's compliance on the MBB beam, where SLSQP
lands within a few per cent. That is the check doing its job, not a bug in the adapter.

If the library has no per-iteration callback (NLopt), call `iterate` from inside the
objective instead and set `reports = "evaluation"`; if it reports nothing until the end,
never call it and set `reports = "final"`. The Pipeline panel shows which.

### The flat view

`flat` (a `FlatProblem`) does the bookkeeping every adapter would otherwise repeat:

| `flat.`              | what it is                                                                 |
| :------------------- | :------------------------------------------------------------------------- |
| `x0`, `lower`, `upper` | start and bounds of the **free** variables (fixed elements are left out)  |
| `n`, `m`             | number of free variables, number of constraints                           |
| `f(x)`, `df(x)`      | objective (scaled, see `flat_objective_scale`) and its gradient            |
| `g(x)`, `dg(x)`      | constraints, **g ≤ 0 satisfied**: the volume budget first, then the scenario's |
| `g_geq(x)`, `dg_geq(x)` | the same in the **g ≥ 0** convention (SciPy's `"ineq"`)                 |
| `reduce(design)`, `expand(x)` | between a design array and the vector                           |
| `constraint_names`   | `["volume budget", "stress", …]`, in `g`'s order                            |

Asking for `f`, `g`, `df` and `dg` at one point costs one physics solve. Any updater can
use the flat view: set `flat_view = True` and call `self.flat_problem(model)` in
`initialize` — Toporia's own MMA does.

## A filter

A filter maps design variables to physical densities, `forward(x)`, and carries the chain
rule back, `backward(x_in, sensitivity)`. Filters stack into a chain, so get the adjoint
exactly right — the conformance check compares it with finite differences. A 3×3 box
average, normalised at the edges:

```python
# example: filter
import numpy as np
from scipy.ndimage import uniform_filter

from toporia.api import Filter


class BoxAverage(Filter):
    """Mean over each element's 3 x 3 neighbourhood (fewer at the edges)."""

    name = "guide_box"
    label = "3x3 box average (guide example)"

    def setup(self, problem, solver):
        ones = np.ones((problem.nely, problem.nelx))
        self.weight = uniform_filter(ones, size=3, mode="constant") * 9   # neighbours per element

    def forward(self, x):
        return uniform_filter(x, size=3, mode="constant") * 9 / self.weight

    def backward(self, x_in, sensitivity):
        # forward is y = B x / w with B symmetric, so the adjoint is B (s / w) —
        # not B s / w: dividing on the wrong side is the classic mistake, and
        # the conformance check catches it.
        return uniform_filter(sensitivity / self.weight, size=3, mode="constant") * 9
```

A filter whose `backward` is deliberately not the derivative (the classic sensitivity
filter) sets `exact_adjoint = False`; one with a continuation schedule implements
`step(iteration)`. Constructor keyword arguments are its `params`.

## A material law

How density becomes stiffness is a part of its own: `stiffness(density, E0, Emin)` and its
`slope`, element-wise. Every physics engine that declares `uses_interpolation` takes it,
and the solver chooses it, `{"type": "linear"}`. The variable-thickness sheet — no
penalisation at all, the problem Rossow and Taylor solved before topology optimisation
had a name — is the baseline every penalised law is measured against:

```python
# example: interpolation
from toporia.api import Interpolation


class Linear(Interpolation):
    """E = Emin + ρ (E0 − Emin): the variable-thickness sheet (Rossow & Taylor 1973)."""

    name = "guide_linear"
    label = "Linear (guide example)"

    def stiffness(self, density, E0, Emin):
        return Emin + density * (E0 - Emin)

    def slope(self, density, E0, Emin):
        return (E0 - Emin) + 0.0 * density      # shaped like the density
```

`toporia check interpolation:<name>` checks E(0) = Emin, E(1) = E0, that E increases, the
slope against finite differences, and a short run.

## A design representation

What the optimiser moves need not be one density per element. A representation turns its
variables `z` into the element density field, `density(z)`, and carries a sensitivity
back, `backward(z, sensitivity)`. It also gives the start design, `initial()`, and the
range of each variable, `bounds()`. The solver chooses it,
`{"type": "guide_mirror"}`, and the model does the rest.

The example is a design that is mirror-symmetric about the vertical centre line.
Only the left half is a variable, so the optimiser sees half as many variables.
The symmetry filter gets the same designs, but it keeps all the variables.

```python
# example: representation
import numpy as np

from toporia.api import Representation


class Mirror(Representation):
    """The left half of the element densities; the right half is its mirror image."""

    name = "guide_mirror"
    label = "Mirror-symmetric (guide example)"
    # One variable sets two elements, so an update rule that moves each element's
    # density on its own (OC, BESO) cannot use it; MMA, GCMMA and SLSQP can.
    element_wise = False

    def setup(self, problem):
        self.problem = problem
        columns = np.arange(problem.nelx)
        self.column = np.minimum(columns, problem.nelx - 1 - columns)   # element column -> variable column
        self.shape = (problem.nely, (problem.nelx + 1) // 2)

    def initial(self):
        lower, upper = self.bounds()
        return np.clip(np.full(self.shape, self.problem.scenario.volfrac), lower, upper)

    def bounds(self):
        # A variable may go only where both of its elements may.
        lower, upper = np.zeros(self.shape), np.ones(self.shape)
        np.maximum.at(lower.T, self.column, self.problem.lower_bound.T)
        np.minimum.at(upper.T, self.column, self.problem.upper_bound.T)
        return lower, np.maximum(lower, upper)

    def density(self, z):
        return z[:, self.column]

    def backward(self, z, sensitivity):
        gradient = np.zeros(self.shape)
        np.add.at(gradient.T, self.column, sensitivity.T)   # each variable collects both its elements
        return gradient
```

Set `element_wise = True` only when the variables *are* the element densities. Every
updater that declares `needs_element_densities` (OC, BESO, SiMPL) is then allowed;
otherwise such a pairing is refused before the run, with the reason.
`toporia check representation:<name>` checks the field's shape and range, that the start
design lies within the bounds, `backward` against finite differences, and a short run with
`q4+mma`.

## A continuation schedule

A schedule changes one parameter during the run. `value(completed)` gives the parameter's
value for the iteration after `completed` finished ones, and `finished(completed)` says when
that value stops changing. The solver attaches a schedule to any parameter path whose part
allows it (`schedulable`), for example
`{"path": "interpolation.penal", "type": "guide_cosine", "start": 1, "end": 3}`. The engine
applies it before each iteration and does not stop on its tolerance until it has finished.

The example is a ramp that starts and ends gently, a smooth alternative to equal steps:

```python
# example: schedule
import math

from toporia.api import Param, Schedule


class CosineRamp(Schedule):
    """From start to end over `over` iterations, along half a cosine: no jumps at either end."""

    name = "guide_cosine"
    label = "Cosine ramp (guide example)"
    params = (Param("start", 1.0, "Start", "First value.", min=-1e6, max=1e6),
              Param("end", 3.0, "End", "Last value.", min=-1e6, max=1e6),
              Param("over", 40, "Over", "Iterations the ramp takes.", min=1, max=10000))

    def __init__(self, start=1.0, end=3.0, over=40):
        self.start, self.end, self.over = float(start), float(end), int(over)

    def value(self, completed):
        if completed >= self.over:
            return self.end
        fraction = 0.5 - 0.5 * math.cos(math.pi * completed / self.over)
        return self.start + fraction * (self.end - self.start)

    def finished(self, completed):
        return completed >= self.over
```

To let a parameter of your own part be scheduled, list it in the part's `schedulable`.
If other values are derived from it when the run starts, also give the part a
`set_parameter(name, value)` that updates them.

`toporia check schedule:<name>` checks that the values are finite, that the schedule
finishes and then stays put, and a short run.

**Several versions of one design** (robust design, uncertain loads) need no plugin; they
are a solver setting:
`{"path": "filters[1].eta", "values": [0.75, 0.5, 0.25], "combine": "worst"}`
evaluates every design eroded, intermediate and dilated, and minimises the worst. See
[`framework/parts/variants.py`](../toporia/framework/parts/variants.py).

## A post-processor

A post-processor makes something of the finished design: numbers, files, or both. It does
not change the optimisation. It is switched on in the run's Output section,
`output.postprocess = [{"type": "guide_perimeter"}]`. Its numbers appear in `run.json`, and
in Compare Methods they appear as a column for every method. `process(result)` receives:

- the final `result.density`, the meshed `result.problem`, and the `result.run`;
- `result.solid()`, the black-and-white design: the threshold's when one ran before it,
  else density ≥ 0.5.

It writes files through `result.file(name)`. The example measures the outline length of the
black-and-white design, a common measure of how intricate a design is:

```python
# example: postprocessor
import numpy as np

from toporia.api import PostProcessor


class Perimeter(PostProcessor):
    """Length of the boundary between solid and void, in mm, counted along element edges."""

    name = "guide_perimeter"
    label = "Perimeter (guide example)"

    def process(self, result):
        solid = np.pad(result.solid(), 1).astype(int)
        across_x = np.abs(np.diff(solid, axis=1)).sum()      # vertical element edges
        across_y = np.abs(np.diff(solid, axis=0)).sum()      # horizontal element edges
        problem = result.problem
        return {"perimeter_mm": float(across_x * problem.dy + across_y * problem.dx)}
```

`toporia check postprocessor:<name>` checks that the metrics are plain values, that the
files it names exist and are not empty, that the design is left unchanged, and that a
second run gives the same numbers.

## A response

A response is a scalar to minimise or constrain. If it can be computed from the density
alone, `requires = ()`; if it needs the physics, list the features it needs (below).
`evaluate` returns a `ResponseValue` whose gradient is with respect to the **physical
density** — the model applies the filter adjoint. A constraint is normalised so that
`value ≤ 0` means satisfied. The measure of non-discreteness (Sigmund 2007) as a limit on
grey material:

```python
# example: response
import numpy as np

from toporia.api import CONSTRAINT_ROLE, Param, Response, ResponseValue


class GreyLevel(Response):
    """M = 4/n · Σ ρ(1 − ρ): 0 for a black-and-white design, 1 for uniform grey."""

    name = "guide_grey"
    label = "Grey material (guide example)"
    roles = (CONSTRAINT_ROLE,)
    requires = ()                    # computed from the density alone
    params = (Param("limit", 0.2, "Grey limit", "Largest allowed measure of non-discreteness.",
                    min=0.0, max=1.0, step=0.05, decimals=3),)

    def evaluate(self, state, gradient=True):
        rho, limit = state.density, self.settings["limit"]
        value = 4.0 * np.mean(rho * (1.0 - rho))
        if not gradient:
            return ResponseValue(value / limit - 1.0)
        return ResponseValue(value / limit - 1.0, 4.0 * (1.0 - 2.0 * rho) / rho.size / limit)
```

It is then offered by every model whose engine provides what it requires — here, every
model. If the defaults make the gradient deliberately inexact (stress's adaptive scaling),
give `gradient_check_settings` for the check.

## A physics engine

A physics engine solves a density for a state and answers questions about it. Which
questions is declared in `provides`; a response can run on every engine that provides
the features it `requires`:

| feature           | methods to implement                                                         | used by          |
| :---------------- | :--------------------------------------------------------------------------- | :--------------- |
| (always)          | `initialize(problem, settings)`, `solve(density)` → state with `.density`, `.weights` | all       |
| `ELASTIC_ENERGY`  | `stiffness_slope(state)`, `compliance(state, case)`, `strain_energy(state, case)` | compliance |
| `STRESS`          | `element_stress`, `stress_load`, `adjoint`, `mutual_energy`                  | stress           |

Displacements and adjoint vectors stay opaque to responses — they only pass them from
one engine method to another — so no response depends on your degree-of-freedom
numbering. Turn the engine into a model with one declaration:

```python
from toporia.api import AssembledModel
from my_package.fe import MyEngine


class MyModel(AssembledModel):
    name, label = "my_engine", "My engine"
    physics = MyEngine
```

The filters, the responses and every updater then work with it.
[`plugins/physics/q4_plane_stress.py`](../toporia/plugins/physics/q4_plane_stress.py) is the
reference engine in 2-D, [`plugins/physics/h8_solid.py`](../toporia/plugins/physics/h8_solid.py)
in 3-D. A physics that brings its own gradients (a pyMOTO network, an AD
framework) can instead be a whole `Model` — see
[`plugins/models/pymoto_elastic.py`](../toporia/plugins/models/pymoto_elastic.py).

## 2-D, 3-D, or both

A scenario with a depth (`Lz > 0`) is a 3-D problem. Every element field then has the shape
`(nelz, nely, nelx)` instead of `(nely, nelx)`; use `problem.shape` and `problem.dims`
rather than `nely` and `nelx`. Each part says where it works with a class attribute:

```python
dims = (2, 3)        # 2-D and 3-D; (2,) for plane problems only, (3,) for 3-D only
```

Updaters, material laws, responses and schedules default to `dims = None`, meaning any
dimension; they never look at the mesh. Filters, representations, post-processors and
physics engines default to `(2,)`. Only widen that once the part handles the third axis.
A part that does not work in the problem's dimension is refused before the run, with the
parts that do. `toporia check` runs a 3-D-only part on the same problems extruded.

## Optional dependencies

If your plugin needs a package Toporia does not require, import it inside your methods
(not at module level) and declare it:

```python
dependencies = ("nlopt",)
```

Where it is missing, the GUI greys the plugin out with the install command, and a run
asking for it stops at once with that command — instead of failing part-way.

## Packaging, outside this repository

Put the plugin in your own package, import only from `toporia.api`, and declare it in your
`pyproject.toml`:

```toml
[project.entry-points."toporia.updaters"]
my_optimisers = "my_package.optimisers"            # every plugin class in a module
my_slsqp      = "my_package.optimisers:MySLSQP"    # or a single class
```

After `pip install my_package` the plugins appear everywhere Toporia's own do;
`toporia list` shows which package each one came from. A plugin that fails to import is
reported (in `toporia list` and the GUI's log) and the others still load. In a notebook,
`UPDATERS.register(MyUpdater)` does the same for one session.

## Checklist

- [ ] `name`, `label`, `params` declared; citation in the module docstring
- [ ] capabilities honest: `objectives`, `max_constraints` / `requires` / `exact_adjoint` / `dims`
- [ ] optional packages in `dependencies`, imported lazily
- [ ] `toporia check kind:name` passes
- [ ] a run from the GUI looks right, and the Pipeline panel describes it correctly
- [ ] the folder README's row says ✅ with a link to the file
