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

**Status: 4 in Toporia · 0 with open code · 1 paper only**

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
| ✅ When the design settles | [`settled.py`](settled.py) | `settled` | start, then × `factor` (or + `step`) each time the design change has been below `change_below`, within `min_every`–`max_every` iterations per level, then `end` | Heaviside β continuation that waits for the design (Wang, Lazarov & Sigmund 2011) |

## 📄 Candidates

| Schedule | Reference | What it adds |
| :-- | :-- | :-- |
| 📄 Continuation-free projection | Guest, Asadpoure & Ha, *SMO* 2011 | Removes the need for a β schedule by reformulating the projection; useful as the baseline a schedule is compared with. It is a filter (a different projection function), not a schedule: nothing changes over time, so it belongs in `plugins/filters`. |

## Waiting for the design: convergence-triggered continuation

**What.** The `settled` schedule raises a parameter when the design has *settled*, not on a
clock. Each level lasts at least `min_every` iterations; it is left as soon as the design
change has been below `change_below` for `settle` iterations in a row, or at the latest after
`max_every`. Each rise multiplies by `factor` (or adds `step` when that is above 0), up to
`end`. Without it, β = 1, 2, 4, … either sharpens before the layout is found or idles on a
design that settled long ago.

**How it sees the design.** The engine tells every schedule the design change after each
iteration through the optional hook `observe(completed, change)` (default: ignored, so
`steps`, `geometric` and `linear` are untouched; see
[`framework/parts/schedule.py`](../../framework/parts/schedule.py)). If nobody calls it, the
schedule is simply "every `max_every` iterations".

**When.** Projection or SIMP-penalty continuation where the right moment depends on the
problem. Set `change_below` above the solver's `tol`, otherwise the stop on `tol` is held
(as for any moving schedule) until the max-iterations fallback has fired. In the MBB
comparison of `tests/plugins/test_schedules.py` the design change of the OC update stays
above 0.03 for long stretches at large β, so the fallback decides much of the time and the
run is not faster than the fixed clock; the schedule pays off when the design does settle.

**Use it.**

- **Config:** `solver.schedules = [{"path": "filters[1].beta", "type": "settled", "start": 1, "end": 64, "change_below": 0.03, "min_every": 10, "max_every": 40}]`
- **GUI:** Schedules panel, pick *When the design settles* for the parameter (a Heaviside β needs a Heaviside filter in the filter list).
- **CLI:**

```
toporia run "MBB Beam" --set 'method=q4+oc' \
  --set 'filter_specs=[{"type":"density"},{"type":"heaviside","beta":1.0}]' \
  --set 'schedules=[{"path":"filters[1].beta","type":"settled","start":1,"end":16,"change_below":0.03,"min_every":10,"max_every":40}]'
```

**Fixed projection without beta continuation** is available as
`MBB Beam (Fixed Projection)`: density filter, fixed Heaviside beta=16 and conservative
MMA settings. Setting `beta_max` equal to `beta` disables built-in doubling; no schedule
is added. The explicit asymptote recipe comes from
[Høghøj & Träff, section 3.1](https://arxiv.org/html/2102.12999#S3.SS1), which credits
[Guest, Asadpoure & Ha (2011)](https://doi.org/10.1007/s00158-011-0676-1).
This corrects the earlier claim here that eliminating continuation necessarily needs
a different projection filter. The full Guest paper's additional variants have not
been reproduced. Sharpness and optimizer tuning remain problem dependent; this recipe
does not guarantee binary designs or work with arbitrary updaters. The bounded
[validation recipe](../../../experiments/fixed_projection.py) reports grayness and volume.

## Several versions of one design: robust formulations

Some formulations evaluate every design several times instead of changing a parameter
over time. The best-known is the robust formulation of Wang, Lazarov & Sigmund (2011):
the design is projected eroded, intermediate and dilated, and the worst of the three is
minimised. This is a solver setting, not a schedule; see
[`framework/parts/variants.py`](../../framework/parts/variants.py):

```python
solver.variants = {"path": "filters[1].eta", "values": [0.75, 0.5, 0.25], "combine": "worst"}
```

**The ready-made recipe.** The preset **`MBB Beam (Robust)`**
([`problems/mbb_beam_robust.py`](../problems/mbb_beam_robust.py)) ships all of it: a density
filter followed by a Heaviside projection, the three η values 0.75 / 0.5 / 0.25 as variants
(worst case, the intermediate design shown), and the `geometric` schedule on
`filters[1].beta`, 1 → 64 doubled every 25 iterations. The paper is
[Wang, Lazarov & Sigmund (2011)](https://doi.org/10.1007/s00158-010-0602-y); the η triplet is
theirs, the β sequence is the usual doubling continuation rather than a copy of their
iteration counts. Use it:

- **GUI:** pick `MBB Beam (Robust)` in the problem list; the Variants and Schedules panels
  are filled in. On any other problem, add a Heaviside filter, press the robust button in
  the Variants panel, and add a geometric schedule on the Heaviside β.
- **CLI:** `toporia run "MBB Beam (Robust)"`; `toporia export "MBB Beam (Robust)" DIR` writes
  the scenario and solver JSON (with `variants` and `schedules`) to edit; to use it on
  another problem, `toporia run "<problem>" DIR/solver.json`.

Each design costs three physics solves, which the run's solve count shows. In the GUI it is the **Variants (robust design)** panel, and its button fills in the robust
projection. The same setting covers uncertain loads, e.g. `load_cases[0].Fa` at three
angles, and an expected value (`"combine": "mean"`).

## Writing one

Subclass `Schedule` and give it `name`, `label` and `params`; the constructor takes each one
as a keyword. Then implement two methods (and, optionally, `observe(completed, change)` to see the design change after each iteration, as `settled` does):

- `value(completed)`, the value for the iteration after `completed` finished ones;
- `finished(completed)`, which says when that value stops changing.

Then run `toporia check schedule:<name>`. It checks that the values are finite, that the
schedule finishes and stays put afterwards, and a short run in which it drives a Heaviside
sharpness.

## References

- J. K. Guest, J. H. Prévost, T. Belytschko, "Achieving minimum length scale in topology optimization using nodal design variables and projection functions", *IJNME* 61 (2004) 238–254.
- F. Wang, B. S. Lazarov, O. Sigmund, "On projection methods, convergence and robust formulations in topology optimization", *SMO* 43 (2011) 767–784.
- J. K. Guest, A. Asadpoure, S.-H. Ha, "Eliminating beta-continuation from Heaviside projection and density filter algorithms", *SMO* 44 (2011) 443–453.
