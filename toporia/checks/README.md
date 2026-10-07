# `toporia/checks` — the conformance test

What a plugin must pass before it is marked ✅. Point it at a class and it checks
everything Toporia relies on, then says what passed, what failed and why:

```python
from toporia.checks import conformance
conformance(MyUpdater).assert_ok()      # in a test
print(conformance(MyUpdater))           # a readable report
```

or `toporia check updater:my_updater` on the command line, or **Check Parts** in the GUI's
mode menu (every part of the selected pipeline).

```
checks/
├── __init__.py     conformance(), all_plugins(), parts_of(): the entry point
├── report.py       Report and Check: one line per check, PASS / FAIL / skip
├── common.py       the benchmark problems, finite differences, thread checks
├── updater.py          a short run with holes; the MBB benchmark within 10 % of OC
├── model.py            shapes, bounds, every gradient (also physics engines)
├── representation.py   field shape and range, start in bounds, backward()
├── filter.py           shape and range, the adjoint against finite differences
├── interpolation.py    E(0) = Emin, E(1) = E0, increasing, slope vs finite differences
├── response.py         the gradient on every engine that can compute it
├── schedule.py         finite values, a finish it keeps, a short run driving a projection
├── postprocess.py      plain metrics, the files it names, the design untouched, repeatable
└── method.py           a whole method: a short run
```

| Plugin | What is checked |
| :--- | :--- |
| every plugin | name, label, parameters that resolve to their defaults |
| updater | a short run on the Drone Arm (holes, solid rings): finite, inside the bounds, no thread left behind; the MBB benchmark under the engine's stopping rule, within the volume budget and within 10 % of optimality criteria's compliance |
| model, physics engine | shapes and bounds, `volume_of` against `evaluate`, values with and without gradients, every gradient against central finite differences |
| representation | the field's shape and range, the start design within the bounds, `backward` against finite differences, a short run with MMA |
| filter | shape and range; the adjoint against finite differences, unless the filter declares `exact_adjoint = False` |
| interpolation | void is void and solid is solid, stiffness increases with density, `slope` against finite differences, a short run |
| schedule | finite values, a finish it keeps, a short run in which it drives a Heaviside sharpness |
| post-processor | plain metrics, every file it names written, the design left unchanged, the same numbers twice |
| response | its gradient on every engine that provides the features it requires |
| whole method | a short run |

The checks use only the public plugin interfaces, so they apply unchanged to a plugin
that lives in another package. A part that works only in 3-D (`dims = (3,)`) is checked
on the same problems extruded two elements deep, with the 3-D model in place of the 2-D one. A failed check names the exception and the line it came
from. The guide to writing plugins is [`docs/writing-plugins.md`](../../docs/writing-plugins.md).
