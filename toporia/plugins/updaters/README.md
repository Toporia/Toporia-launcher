# Updaters — how the design moves

An updater turns a model's `Evaluation` (objective, volume, gradients) into the next
design. It knows nothing about the physics that produced the numbers, so **every updater
works with every model** — see [`framework/parts/composition.py`](../../framework/parts/composition.py).

**Status: 12 in Toporia · 8 with open code · 3 paper only**

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
| ✅ MMA (NLopt) | [`nlopt_optimizers.py`](nlopt_optimizers.py) | `nlopt_mma` | any number | NLopt's `LD_MMA`: Svanberg's method of moving asymptotes with the conservative-approximation safeguard. Optional dependency (`pip install nlopt`). Within 2 % of OC on the MBB benchmark. |
| ✅ CCSAQ (NLopt) | [`nlopt_optimizers.py`](nlopt_optimizers.py) | `nlopt_ccsaq` | any number | NLopt's `LD_CCSAQ`: MMA's globally convergent relative with a quadratic model (Svanberg 2002). Optional dependency. |
| ✅ SLSQP (NLopt) | [`nlopt_optimizers.py`](nlopt_optimizers.py) | `nlopt_slsqp` | any number | NLopt's `LD_SLSQP` (Kraft 1988), the same algorithm as `scipy_slsqp` from a second implementation. Dense, so coarse meshes only. Optional dependency. |
| ✅ Augmented Lagrangian + L-BFGS (NLopt) | [`nlopt_optimizers.py`](nlopt_optimizers.py) | `nlopt_auglag` | any number | NLopt's `AUGLAG` with `LD_LBFGS` inside: constraints become penalties with multiplier updates, bound-constrained subproblems are solved by L-BFGS. Optional dependency. |
| ✅ trust-constr (SciPy) | [`scipy_minimize.py`](scipy_minimize.py) | `scipy_trust_constr` | any number | Trust-region SQP / interior point with exact gradients; see [its entry](#scipy-optimisers-in-scipy_minimizepy). Dense, so coarse meshes only. Within 1 % of OC on the MBB benchmark. |

### SciPy optimisers in `scipy_minimize.py`

One more `scipy.optimize.minimize` method, wrapped like `scipy_slsqp` (the adapter calls
the library, [`ExternalOptimizer`](../../framework/optimisers/external_loop.py) runs it in a
background thread). It takes bounds and any number of constraints, and shows up in the GUI
(Method ▸ Physics model + updater ▸ Updater) and in `toporia list` automatically, with
its parameters. Pair it with any model, e.g. `q4+scipy_trust_constr`:

```
toporia run "MBB Beam" --set method=q4+scipy_trust_constr
```

- **`scipy_trust_constr`**: SciPy's
  [`trust-constr`](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-trustconstr.html),
  a trust-region method (Conn, Gould & Toint, *Trust-Region Methods*, SIAM 2000) that
  handles the volume budget (and a stress limit, if the scenario has one) as a
  `NonlinearConstraint` with exact Jacobians. The curvature model defaults to SR1: on
  compliance under SIMP it reached OC's compliance in about 50 iterations where BFGS had not
  after 200. The objective is scaled to start at 100 for the same reason (measured, see the
  comment in the file). Parameters: iterations, tolerance, initial trust radius, Hessian.

COBYQA and COBYLA (gradient-free) were tried with the same adapter but are not registered: on the MBB benchmark (192 variables) both end about 50 % above OC after 200 iterations, so they cannot pass the conformance benchmark.

Every updater enforces the volume budget. Only the pyMOTO, SciPy and NLopt updaters can enforce a
**second** constraint, such as a stress limit: `q4+pymoto_mma` runs a stress-limited
design on Toporia's own solver. **None of Toporia's own updaters can yet** — see the
augmented Lagrangian entry below.

## NLopt updaters

[NLopt](https://nlopt.readthedocs.io) is one C library with a common interface to dozens of
optimisers. [`nlopt_optimizers.py`](nlopt_optimizers.py) wraps the four gradient-based
algorithms that accept bounds and any number of nonlinear inequality constraints, so they
enforce the volume budget and any further limit the scenario adds (a stress limit, say):

| Updater | NLopt algorithm | What it is |
| :-- | :-- | :-- |
| `nlopt_mma` | [`LD_MMA`](https://nlopt.readthedocs.io/en/latest/NLopt_Algorithms/#mma-method-of-moving-asymptotes-and-ccsa) | Svanberg's method of moving asymptotes, with the conservative-approximation check of the 2002 paper: a step that would make the model optimistic is retried with a stiffer penalty. The same family as Toporia's own `mma`, from an independent implementation. |
| `nlopt_ccsaq` | [`LD_CCSAQ`](https://nlopt.readthedocs.io/en/latest/NLopt_Algorithms/#mma-method-of-moving-asymptotes-and-ccsa) | CCSA with a quadratic (rather than separable-rational) model; MMA's globally convergent relative. |
| `nlopt_slsqp` | [`LD_SLSQP`](https://nlopt.readthedocs.io/en/latest/NLopt_Algorithms/#slsqp) | Kraft's sequential least-squares quadratic programming. Dense matrices, so coarse meshes only. |
| `nlopt_auglag` | [`AUGLAG`](https://nlopt.readthedocs.io/en/latest/NLopt_Algorithms/#augmented-lagrangian-algorithm) with [`LD_LBFGS`](https://nlopt.readthedocs.io/en/latest/NLopt_Algorithms/#low-storage-bfgs) | Augmented Lagrangian (Conn, Gould & Toint; Birgin & Martínez): constraints are folded into the objective with multipliers and a penalty, and each bound-constrained subproblem is solved by L-BFGS. |

**Install:** `pip install nlopt` (or `pip install toporia[nlopt]`). Without it the four are
listed but greyed out, with the install command shown.

**Use:** the method is `<model>+<updater>`, so

```
toporia run "MBB Beam" --set method=q4+nlopt_mma
toporia run "MBB Beam" --set method=q4+nlopt_auglag --set nlopt_maxeval=1000
toporia benchmark --methods q4+oc q4+nlopt_mma q4+nlopt_ccsaq q4+nlopt_slsqp q4+nlopt_auglag
toporia check updater:nlopt_mma
```

In the GUI they appear in the updater drop-down of the method panel (`toporia list` shows
the same list), and their parameters appear under it.

**How they run.** NLopt runs its own loop and has no per-iteration callback, so the adapter
(an [`ExternalOptimizer`](../../framework/optimisers/external_loop.py)) runs it in a background
thread and hands the engine each design NLopt evaluates (`reports = "evaluation"`). One
"iteration" in the display is therefore one function evaluation, trial points of NLopt's
inner loops included, and the iteration counts of these updaters are not comparable with
`oc` or `mma`: compare the `solves` column. Points that land almost on top of the last one
shown are skipped (`nlopt_report_step`), otherwise the engine's tolerance would end the
run on the first near-duplicate trial point. Parameters: `nlopt_maxeval` and
`nlopt_ftol_rel` (NLopt's own stopping rule, alongside the engine's), `nlopt_report_step`,
`nlopt_rho_init` (MMA and CCSAQ: smaller means a bolder first step) and
`nlopt_local_maxeval` (AUGLAG: evaluations per L-BFGS subproblem).
## Writing one for an outside optimiser

The full guide, with a worked example of every plugin kind, is
[`docs/writing-plugins.md`](../../../docs/writing-plugins.md).

Almost every optimiser from a library wants a vector, bounds and callbacks. Set
`flat_view = True` on the updater and call `self.flat_problem(model)` in `initialize`:
the [`FlatProblem`](../../framework/optimisers/flat_view.py) it returns gives `x0`, `lower`, `upper`, `f`,
`df`, `g`, `dg` (and `g_geq`, `dg_geq` for SciPy's sign convention), with the fixed
elements left out, the volume budget as the first constraint, an optional objective
scaling (`flat_objective_scale`), and a cache so one point costs one physics solve.
[`mma.py`](mma.py) and [`pymoto_optimizers.py`](pymoto_optimizers.py) are both built on
it. Every run counts its physics solves itself (`solves` in the history and the
console), so an updater that re-evaluates trial designs is compared fairly.

If the library insists on running its own loop (SciPy's `minimize`, NLopt, IPOPT),
subclass [`ExternalOptimizer`](../../framework/optimisers/external_loop.py) instead and write one method,
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
- S. G. Johnson, [The NLopt nonlinear-optimization package](https://github.com/stevengj/nlopt).
- D. Kraft, "A software package for sequential quadratic programming", DFVLR-FB 88-28 (1988).
- A. R. Conn, N. I. M. Gould, P. L. Toint, "A globally convergent augmented Lagrangian algorithm…", *SIAM J. Numer. Anal.* 28 (1991) 545–572; E. G. Birgin, J. M. Martínez, *Optim. Methods Softw.* 23 (2008) 177–195.
- K. Svanberg, "A class of globally convergent optimization methods…", *SIAM J. Optim.* 12 (2002) 555–573.
- B. Keith, D. Kim, B. S. Lazarov, T. M. Surowiec, "A simple introduction to the SiMPL method for density-based topology optimization", *SMO* 68 (2025); [arXiv:2411.19421](https://arxiv.org/abs/2411.19421).
- X. Huang, Y. M. Xie, "Convergent and mesh-independent solutions for the bi-directional evolutionary structural optimization method", *FEAD* 43 (2007) 1039–1049.
- O. Sigmund, "On the usefulness of non-gradient approaches in topology optimization", *SMO* 43 (2011) 589–596.
