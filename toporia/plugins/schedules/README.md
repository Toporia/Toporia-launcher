# Schedules: parameters that change during a run (continuation)

Many methods only work, or only match their paper, when a parameter is tightened while the
run goes on:

- the SIMP penalty is raised from 1 to 3, starting from the convex problem;
- the Heaviside sharpness is doubled up to 64;
- a stress p-norm exponent is raised once the design has settled.

A schedule says what value one parameter takes after a given number of completed
iterations. It is a part of its own; see
[`framework/parts/schedule.py`](../../framework/parts/schedule.py). The solver lists the
schedules together with the parameter path each one drives:

```python
solver.schedules = [{"path": "interpolation.penal", "type": "steps",
                     "start": 1, "end": 3, "step": 0.5, "every": 20}]
```

The engine applies every schedule before each iteration and records the value with the
history. In the GUI they are the **Schedules** panel, and the Pipeline box lists them.

**The engine does not stop on its tolerance while a schedule is still moving.** A design that
settles at p = 1, or at a soft projection, is not the answer to the problem at the end of the
schedule. The same goes for a part's own built-in continuation: the Heaviside filter's β
doubling and the routing filter's ramp hold the stop the same way. A run that reaches its
iteration limit first says which schedules had not finished.

**Which parameters can change.** Each part lists them in `schedulable`. Not every parameter
can: the density filter's radius is built into its weights when the run starts. A schedule on
any other parameter is refused before the run, with the list of parameters that part *can*
change. Today these can be scheduled:

| Part | Parameters |
| :-- | :-- |
| SIMP | `penal` |
| RAMP | `q` |
| Heaviside projection | `beta`, `eta` |
| Moving morphable components | `edge_width` |
| von Mises stress | `p` |
| OC, MMA | `move` |

A schedule on the Heaviside `beta` replaces the filter's built-in doubling, so the two never
both set it.

**Status: 3 in Toporia · 0 with open code · 2 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here, registered, passes `toporia check schedule:<name>`. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Schedule | File | Name | Values | Typical use |
| :-- | :-- | :-- | :-- | :-- |
| ✅ Equal steps | [`steps.py`](steps.py) | `steps` | start, start + step, … every `every` iterations, then `end` | SIMP / RAMP penalty continuation |
| ✅ Multiply by a factor | [`geometric.py`](geometric.py) | `geometric` | start, start × factor, … every `every` iterations, then `end` | Heaviside β doubling (Guest, Prevost & Belytschko 2004) |
| ✅ Linear ramp | [`linear.py`](linear.py) | `linear` | `start` for `after` iterations, then a straight line to `end` over `over` | Switching a fabrication rule on gradually; narrowing MMC edges |

## 📄 Candidates

| Schedule | Reference | What it adds |
| :-- | :-- | :-- |
| 📄 Convergence-triggered continuation | Common practice in the projection literature, e.g. Wang, Lazarov & Sigmund, *SMO* 2011 | Raises the parameter when the design has settled, instead of after a fixed number of iterations. Needs `value()` to see the design change as well as the iteration count. |
| 📄 Continuation-free projection | Guest, Asadpoure & Ha, *SMO* 2011 | Removes the need for a β schedule by reformulating the projection; useful as the baseline a schedule is compared with. |

## Several versions of one design: robust formulations

Some formulations evaluate every design several times instead of changing a parameter
over time. The best-known is the robust formulation of Wang, Lazarov & Sigmund (2011):
the design is projected eroded, intermediate and dilated, and the worst of the three is
minimised. This is a solver setting, not a schedule; see
[`framework/parts/variants.py`](../../framework/parts/variants.py):

```python
solver.variants = {"path": "filters[1].eta", "values": [0.75, 0.5, 0.25], "combine": "worst"}
```

In the GUI it is the **Variants (robust design)** panel, and its button fills in the robust
projection. The same setting covers uncertain loads, e.g. `load_cases[0].Fa` at three
angles, and an expected value (`"combine": "mean"`).

## Writing one

Subclass `Schedule` and give it `name`, `label` and `params`; the constructor takes each one
as a keyword. Then implement two methods:

- `value(completed)`, the value for the iteration after `completed` finished ones;
- `finished(completed)`, which says when that value stops changing.

Then run `toporia check schedule:<name>`. It checks that the values are finite, that the
schedule finishes and stays put afterwards, and a short run in which it drives a Heaviside
sharpness.

## References

- J. K. Guest, J. H. Prévost, T. Belytschko, "Achieving minimum length scale in topology optimization using nodal design variables and projection functions", *IJNME* 61 (2004) 238–254.
- F. Wang, B. S. Lazarov, O. Sigmund, "On projection methods, convergence and robust formulations in topology optimization", *SMO* 43 (2011) 767–784.
- J. K. Guest, A. Asadpoure, S.-H. Ha, "Eliminating beta-continuation from Heaviside projection and density filter algorithms", *SMO* 44 (2011) 443–453.
