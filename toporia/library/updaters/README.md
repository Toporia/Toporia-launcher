# Updaters — how the design moves

An updater turns a model's `Evaluation` (objective, volume, gradients) into the next
design. It knows nothing about the physics that produced the numbers, so **every updater
works with every model** — see [`core/composition.py`](../../core/composition.py).

**Status: 7 in Toporia · 8 with open code · 3 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here, registered, tested. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Updater | File | Registry name | Constraints | Notes |
| :-- | :-- | :-- | :-- | :-- |
| ✅ Optimality criteria | [`oc.py`](oc.py) | `oc` | volume only | Bisection on one Lagrange multiplier. Needs objective and volume gradients of opposite sign, so compliance only. The top88 update. |
| ✅ Method of moving asymptotes | [`mma.py`](mma.py) | `mma` | volume only | Convex separable subproblem, solved through its dual by bisection. The field's workhorse. |
| ✅ Mirror descent (SiMPL) | [`simpl.py`](simpl.py) | `simpl` | volume only | Steps in `logit(x)`, so bounds hold by construction with no clipping. Its multiplier may be zero, so a non-binding volume budget simply does not act. |
| ✅ BESO, soft kill | [`beso.py`](beso.py) | `beso` | volume only | Binary designs by sensitivity ranking and an evolutionary volume schedule. Brings its own convergence test, because a binary design's max design change never settles. |
| ✅ MMA (pyMOTO) | [`pymoto_optimizers.py`](pymoto_optimizers.py) | `pymoto_mma` | any number | pyMOTO's implementation, for cross-checking ours. Optional dependency. |
| ✅ GCMMA (pyMOTO) | [`pymoto_optimizers.py`](pymoto_optimizers.py) | `pymoto_gcmma` | any number | Globally convergent MMA with an inner loop, for strongly non-linear responses. Optional dependency. |
| ✅ SLSQP (SciPy) | [`scipy_slsqp.py`](scipy_slsqp.py) | `scipy_slsqp` | any number | Sequential quadratic programming (Kraft 1988). Runs its own loop in the background; **the worked example in [`docs/writing-plugins.md`](../../../docs/writing-plugins.md)**. Dense quasi-Newton matrix, so coarse meshes only. Within 3 % of OC on the MBB benchmark. |

Every updater enforces the volume budget. Only the two pyMOTO updaters can enforce a
**second** constraint, such as a stress limit: `q4+pymoto_mma` runs a stress-limited
design on Toporia's own solver. **None of Toporia's own updaters can yet** — see the
augmented Lagrangian entry below.

## Writing one for an outside optimiser

The full guide, with a worked example of every plugin kind, is
[`docs/writing-plugins.md`](../../../docs/writing-plugins.md).

Almost every optimiser from a library wants a vector, bounds and callbacks. Set
`flat_view = True` on the updater and call `self.flat_problem(model)` in `initialize`:
the [`FlatProblem`](../../core/flat.py) it returns gives `x0`, `lower`, `upper`, `f`,
`df`, `g`, `dg` (and `g_geq`, `dg_geq` for SciPy's sign convention), with the fixed
elements left out, the volume budget as the first constraint, an optional objective
scaling (`flat_objective_scale`), and a cache so one point costs one physics solve.
[`mma.py`](mma.py) and [`pymoto_optimizers.py`](pymoto_optimizers.py) are both built on
it. Every run counts its physics solves itself (`solves` in the history and the
console), so an updater that re-evaluates trial designs is compared fairly.

If the library insists on running its own loop (SciPy's `minimize`, NLopt, IPOPT),
subclass [`ExternalOptimizer`](../../core/external.py) instead and write one method,
`run(flat, x0, iterate)`: call the library, call `iterate(x)` wherever it reports a new
design (its per-iteration callback, or its objective if it has no callback), and return
a `Verdict`. The library then runs in a background thread and hands the engine one
design at a time, so the live display, the stopping rule and the Stop button work as for
any other updater, and its own verdict (success, message, its counts) is written to
`run.json`. Set `reports = "evaluation"` or `"final"` when that is all the library can do.

## Candidates — mathematical programming

| Updater | Status | Reference | Why it matters |
| :-- | :-- | :-- | :-- |
| Augmented Lagrangian | 🔗 [PolyStress](https://link.springer.com/article/10.1007/s00158-020-02760-8) | Giraldo-Londoño & Paulino, *PRSA* 2020; *SMO* 2021 | **The missing piece for local constraints.** Turns thousands of local stress limits into a sequence of bound-constrained subproblems; proven to hundreds of millions of constraints. Would let Toporia's own updaters enforce [`responses/stress.py`](../responses/README.md). Subproblem-solver comparison: Silva et al., *IJNME* 2025. |
| Sequential integer linear programming (TOBS) | 🔗 [101-line MATLAB](https://link.springer.com/article/10.1007/s00158-020-02719-9) | Sivapuram & Picelli, *FEAD* 2018; Picelli et al., *SMO* 2021 | Strict {0,1} variables with multiple constraints handled explicitly. `scipy.optimize.milp` ships HiGHS, so no new dependency. |
| CONLIN | 📄 | Fleury, *Struct. Optim.* 1989 | MMA's predecessor: convex linearisation without moving asymptotes. Cheap to write, and the clean way to show what the asymptotes actually buy. |
| SLP with trust region | 🔗 `scipy.optimize` | standard | Linearise and solve with move limits. The usual choice for level-set and feature-mapping problems: few variables, many constraints. (SQP is in Toporia as `scipy_slsqp`.) |
| Interior point (IPOPT) | 🔗 IPOPT | Wächter & Biegler, *Math. Prog.* 2006 | General NLP for small-variable, many-constraint formulations. Used by GPTO and GGP. |
| Modified OC for several constraints | 📄 | Zhou & Rozvany, *Struct. Optim.* 1991 | Extends the OC multiplier search beyond one constraint; historically the alternative to MMA. |

## Candidates — different update logic

| Updater | Status | Reference | Why it matters |
| :-- | :-- | :-- | :-- |
| Hard-kill ESO / BESO variants | 🔗 [BESO2D (RMIT)](https://www.rmit.edu.au/research/centres-collaborations/centre-for-innovative-structures-and-materials/software), [`calculix/beso`](https://github.com/calculix/beso) | Xie & Steven 1993; Huang & Xie 2007, 2010 | Soft kill is implemented here; hard kill removes elements from the mesh entirely. Validity critique worth reading alongside: Zhou & Rozvany, *SMO* 2001. |
| Floating projection | 📄 | Huang, *CMAME* 2021 | Reaches binary designs from a continuous formulation without a projection filter's β continuation. |
| Discrete variable sequential approximation | 🔗 DVTOPCRA | Liang & Cheng 2019 | Integer design variables via sequential approximate integer programming. |
| Adam / L-BFGS on network weights | 🔗 [TOuNN](https://link.springer.com/article/10.1007/s00158-020-02748-4) | Hoyer et al. 2019; Chandrasekhar & Suresh, *SMO* 2021 | What neural reparameterisations use: variables are weights, the volume budget is a penalty rather than a bound. Needed if [`methods/`](../methods/README.md) gains a neural parameterisation. |
| Proportional topology optimisation | 🔗 [ptomethod.org](http://www.ptomethod.org) | Biyikli & To, *PLoS ONE* 2015 | Non-gradient redistribution, no sensitivities. Useful only as a baseline. |
| Metaheuristics (GA, SA, ACO) | 🔗 [topASA](https://github.com/Hossein-Rostami/Topology-Optimization-with-adaptive-Simulated-Annealing) | see Sigmund, *SMO* 2011 | Included so the platform can **demonstrate why they lose**: orders of magnitude more function evaluations at far lower resolution. Not a serious candidate. |

## Notes on what has been measured here

Benchmarks against the reference implementations are recorded in the module docstrings
rather than here, so they stay next to the code they describe. In particular,
[`simpl.py`](simpl.py) carries a measured comparison against `oc` on the MBB beam and an
explicit note that **the paper's reported advantage over OC and MMA is not reproduced** by
the element-wise form implemented here.

## References

- K. Svanberg, "The method of moving asymptotes", *IJNME* 24 (1987) 359–373.
- K. Svanberg, "A class of globally convergent optimization methods…", *SIAM J. Optim.* 12 (2002) 555–573.
- B. Keith, D. Kim, B. S. Lazarov, T. M. Surowiec, "A simple introduction to the SiMPL method for density-based topology optimization", *SMO* 68 (2025); [arXiv:2411.19421](https://arxiv.org/abs/2411.19421).
- X. Huang, Y. M. Xie, "Convergent and mesh-independent solutions for the bi-directional evolutionary structural optimization method", *FEAD* 43 (2007) 1039–1049.
- O. Sigmund, "On the usefulness of non-gradient approaches in topology optimization", *SMO* 43 (2011) 589–596.
