# Updaters — how the design moves

An updater turns a model's `Evaluation` (objective, volume, gradients) into the next
design. It knows nothing about the physics that produced the numbers, so **every updater
works with every model** — see [`framework/parts/composition.py`](../../framework/parts/composition.py).

**Status: 20 in Toporia · 5 with open code · 3 paper only**

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
| ✅ BESO, hard kill | [`beso_hard.py`](beso_hard.py) | `beso_hard` | volume only | Soft-kill BESO's code with removed elements set to exactly the void bound; they return only through filtered neighbour sensitivities. See [its section](#beso-hard-kill--beso_hard). |
| ✅ Adam (augmented Lagrangian) | [`adam.py`](adam.py) | `adam` | volume only | Adam (Kingma & Ba 2015) on the design variables, the budget an augmented-Lagrangian term, bounds by clipping. The updater neural reparameterisations need. See [its section](#adam--adam). |
| ✅ Proportional topology optimisation | [`pto.py`](pto.py) | `pto` | volume only | Budget handed out in proportion to element energy^q, no multiplier or linearisation. A baseline. See [its section](#proportional-topology-optimisation--pto). |
| ✅ TOBS (integer LP) | [`tobs.py`](tobs.py) | `tobs` | volume only | Binary designs by sequential integer linear programming: linearise, then flip elements optimally with HiGHS (`scipy.optimize.milp`). Own convergence test, like BESO. |
| ✅ MMA (pyMOTO) | [`pymoto_optimizers.py`](pymoto_optimizers.py) | `pymoto_mma` | any number | pyMOTO's implementation, for cross-checking ours. Optional dependency. |
| ✅ GCMMA (pyMOTO) | [`pymoto_optimizers.py`](pymoto_optimizers.py) | `pymoto_gcmma` | any number | Globally convergent MMA with an inner loop, for strongly non-linear responses. Optional dependency. |
| ✅ SLSQP (SciPy) | [`scipy_slsqp.py`](scipy_slsqp.py) | `scipy_slsqp` | any number | Sequential quadratic programming (Kraft 1988). Runs its own loop in the background; **the worked example in [`docs/writing-plugins.md`](../../../docs/writing-plugins.md)**. Dense quasi-Newton matrix, so coarse meshes only. Within 3 % of OC on the MBB benchmark. |
| ✅ MMA (NLopt) | [`nlopt_optimizers.py`](nlopt_optimizers.py) | `nlopt_mma` | any number | NLopt's `LD_MMA`: Svanberg's method of moving asymptotes with the conservative-approximation safeguard. Optional dependency (`pip install nlopt`). Within 2 % of OC on the MBB benchmark. |
| ✅ CCSAQ (NLopt) | [`nlopt_optimizers.py`](nlopt_optimizers.py) | `nlopt_ccsaq` | any number | NLopt's `LD_CCSAQ`: MMA's globally convergent relative with a quadratic model (Svanberg 2002). Optional dependency. |
| ✅ SLSQP (NLopt) | [`nlopt_optimizers.py`](nlopt_optimizers.py) | `nlopt_slsqp` | any number | NLopt's `LD_SLSQP` (Kraft 1988), the same algorithm as `scipy_slsqp` from a second implementation. Dense, so coarse meshes only. Optional dependency. |
| ✅ Augmented Lagrangian + L-BFGS (NLopt) | [`nlopt_optimizers.py`](nlopt_optimizers.py) | `nlopt_auglag` | any number | NLopt's `AUGLAG` with `LD_LBFGS` inside: constraints become penalties with multiplier updates, bound-constrained subproblems are solved by L-BFGS. Optional dependency. |
| ✅ trust-constr (SciPy) | [`scipy_minimize.py`](scipy_minimize.py) | `scipy_trust_constr` | any number | Trust-region SQP / interior point with exact gradients; see [its entry](#scipy-optimisers-in-scipy_minimizepy). Dense, so coarse meshes only. Within 1 % of OC on the MBB benchmark. |
| ✅ MMA (mmapy) | [`mmapy_optimizers.py`](mmapy_optimizers.py) | `mmapy_mma` | any number | Svanberg's reference MMA as ported by Arjen Deetman: the yardstick for `mma` and `pymoto_mma`. **GPL-3, optional, install it yourself** — see [below](#gpl-3-optimisers-mmapy-and-nullspace_optimizer). |
| ✅ GCMMA (mmapy) | [`mmapy_optimizers.py`](mmapy_optimizers.py) | `mmapy_gcmma` | any number | Svanberg's globally convergent MMA with its inner iterations, same package. **GPL-3, optional.** |
| ✅ Null-space optimiser | [`nullspace.py`](nullspace.py) | `nullspace` | any number | Feppon's null-space gradient flow: constraints are followed, not penalised. Runs its own loop in the background. **GPL-3, optional.** |

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

Every updater enforces the volume budget. Only the pyMOTO, SciPy, NLopt, mmapy and null-space updaters can enforce a
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
toporia run "MBB Beam" --set method=q4+nlopt_auglag --set method.nlopt_maxeval=1000
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

## TOBS — binary designs by integer linear programming

**What it does.** Like BESO, TOBS keeps every element strictly void or solid, but it does not
rank elements by a threshold. Each iteration it linearises the objective and the volume at the
current binary design and solves an **integer linear program** for the best set of flips
(solid to void, void to solid) with HiGHS, through `scipy.optimize.milp` (no new dependency).
Two parameters keep the linearisation honest: **ε**, the most the volume target may move per
iteration, and **β**, the largest fraction of elements that may flip per iteration. Sensitivities
are averaged with the previous iteration, as in the 101-line code. Started from a full domain it
descends to the budget at ε per iteration, then trades material between places at constant volume.

**When to use it.** When you want a strictly black-and-white result without a projection filter,
and as the natural route to *explicit* constraints on binary designs (an ILP takes any number of
linear rows; this plugin enforces the volume only). Compared with BESO it is less heuristic but
slower per iteration (an ILP each time). On the MBB benchmark it lands within about 5 % of OC on the
final binary design, in the same range as BESO. Use a density or sensitivity filter, as for BESO.

**How to use it.** The method is `q4+tobs` (any model that gives element densities; refused with
bars or other representations, like OC and BESO).

```
toporia run "MBB Beam" --set method=q4+tobs
toporia run "MBB Beam" --set method=q4+tobs --set method.epsilon=0.01 --set method.beta=0.02
toporia check updater:tobs
```

In the GUI, choose **TOBS (integer LP)** among the methods; its parameters (constraint relaxation
ε, flip limit β, sensitivity averaging, tolerance, start from solid) appear with the method.

**Links.** [101-line MATLAB code paper](https://doi.org/10.1007/s00158-020-02719-9) (Picelli,
Sivapuram, Xie, *SMO* 2021), with code; original method: Sivapuram & Picelli, *FEAD* 139 (2018) 49–61.

## BESO, hard kill — `beso_hard`

**What it does.** Soft-kill BESO's ranking, volume schedule, addition limit and convergence test
([`beso.py`](beso.py); `beso_hard` subclasses it, nothing is copied), but a removed element is set
to exactly the void bound (0, so Emin stiffness: to the solver it is absent) instead of `void_density`.
Under SIMP such an element has no strain energy and so no sensitivity of its own: it can come back only
through the **filtered** sensitivities of its solid neighbours. The mesh is not literally shrunk (the stiffness
matrix would change size every iteration).

**When to use it.** To see the hard-kill behaviour that Zhou & Rozvany (2001) criticised: re-admission is decided by
the filter's smoothing, and with no filter nothing ever returns. With the default density filter it behaves
like soft kill on the MBB beam (compliance 285.4 against 285.2, OC 274.5).

**How to use it.** `q4+beso_hard` (element densities only, like `beso`).

```
toporia run "MBB Beam" --set method=q4+beso_hard --set method.er=0.02
toporia check updater:beso_hard
```

GUI: choose **BESO (hard kill)** in the Updater picker; the same parameters as BESO except the void density.

**Links.** Huang & Xie, *Evolutionary Topology Optimization of Continuum Structures*, Wiley 2010;
Zhou & Rozvany, *SMO* 21 (2001) 80–83; [BESO2D (RMIT)](https://www.rmit.edu.au/research/centres-collaborations/centre-for-innovative-structures-and-materials/software),
[`calculix/beso`](https://github.com/calculix/beso).

## Adam — `adam`

**What it does.** Adam (Kingma & Ba, ICLR 2015) on the design variables, with the volume budget folded in as an
**augmented-Lagrangian** term (multiplier updated every iteration; switch it off for the plain quadratic penalty
TOuNN uses). The objective is normalised by its first value so the learning rate means the same on every problem.
**Bounds by clipping**, not a sigmoid: pinned (passive/void) elements are honoured exactly, a saturated sigmoid
variable can hardly come back, and projected Adam is what runs on network weights (infinite bounds, so the clip does nothing).

**When to use it.** It is the updater a neural reparameterisation will use, where the variables are weights and
a constraint cannot be a bound; it also runs on plain element densities. On the MBB beam it lands within 1 % of OC (277.2 vs 274.5),
but it is a penalty method: the budget is held to a percent or so, not exactly (the plain-density run is tuned for it:
Adam's usual β₁ = 0.9 ends 7–9 % over the budget, so the default is 0.5), and the learning rate must decay or the design
never settles under the engine's tolerance.

**How to use it.** `q4+adam`.

```
toporia run "MBB Beam" --set method=q4+adam --set method.lr=0.05 --set method.penalty=3
toporia check updater:adam
```

GUI: **Adam (augmented Lagrangian)** in the Updater picker; parameters learning rate, decay, β₁, β₂, penalty, multiplier update.

**Links.** [Adam, arXiv:1412.6980](https://arxiv.org/abs/1412.6980); [TOuNN](https://link.springer.com/article/10.1007/s00158-020-02748-4)
(Chandrasekhar & Suresh, *SMO* 63 (2021) 1135–1149); Nocedal & Wright, *Numerical Optimization* §17.4.

## Proportional topology optimisation — `pto`

**What it does.** Each iteration the volume budget is allocated to the elements in proportion to their energy raised to *q*;
the proportionality constant is found by bisection, so the budget is spent exactly and the cap-and-redistribute loop of the
paper is covered by the clipping. The old density is partly retained (`relax`) and moves are limited (`move`).
**Energy proxy:** an `Evaluation` carries no element strain energies, only gradients, so the updater uses the objective gradient
magnitude −dC/dx, which for compliance under SIMP is the energy times p/x (the PTO papers treat the two as equivalent); no framework change.

**When to use it.** As a baseline: no multiplier, no linearisation, no theory. Undamped it flip-flops and ends 70–100 % above OC; with
the defaults (q = 3, retained material 0.8) it reaches 287.5 against OC's 274.5 (+4.8 %). Expect noisier convergence than OC: it usually uses all 200 iterations, and the result moves a few percent with
`q` and `relax`.

**How to use it.** `q4+pto`.

```
toporia run "MBB Beam" --set method=q4+pto --set method.q=3 --set method.relax=0.2
toporia check updater:pto
```

GUI: **Proportional topology optimisation** in the Updater picker; parameters move limit, exponent q, retained material.

**Links.** Biyikli & To, *PLoS ONE* 10 (2015) e0145041; [ptomethod.org](http://www.ptomethod.org).

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
| CONLIN | 📄 | Fleury, *Struct. Optim.* 1989 | MMA's predecessor: convex linearisation without moving asymptotes. Cheap to write, and the clean way to show what the asymptotes actually buy. |
| SLP with trust region | 🔗 `scipy.optimize` | standard | Linearise and solve with move limits. The usual choice for level-set and feature-mapping problems: few variables, many constraints. (SQP is in Toporia as `scipy_slsqp`.) |
| Interior point (IPOPT) | 🔗 IPOPT | Wächter & Biegler, *Math. Prog.* 2006 | General NLP for small-variable, many-constraint formulations. Used by GPTO and GGP. |
| Modified OC for several constraints | 📄 | Zhou & Rozvany, *Struct. Optim.* 1991 | Extends the OC multiplier search beyond one constraint; historically the alternative to MMA. |

## Candidates — different update logic

| Updater | Status | Reference | Why it matters |
| :-- | :-- | :-- | :-- |
| Floating projection | 📄 | Huang, *CMAME* 2021 | Reaches binary designs from a continuous formulation without a projection filter's β continuation. |
| Discrete variable sequential approximation | 🔗 DVTOPCRA | Liang & Cheng 2019 | Integer design variables via sequential approximate integer programming. |
| Metaheuristics (GA, SA, ACO) | 🔗 [topASA](https://github.com/Hossein-Rostami/Topology-Optimization-with-adaptive-Simulated-Annealing) | see Sigmund, *SMO* 2011 | Included so the platform can **demonstrate why they lose**: orders of magnitude more function evaluations at far lower resolution. Not a serious candidate. |

## GPL-3 optimisers: mmapy and nullspace_optimizer

Two updaters wrap libraries licensed **GPL-3**, while Toporia is Apache-2.0. They are
therefore never bundled and never required: each adapter imports its library only when a
run starts, declares it in `dependencies` (so the GUI greys the updater out and shows the
install command when it is missing, and `toporia list` marks it), and you install the
library yourself. Installing it is your decision, and the GPL then applies to the
combination you run. Without them everything else in Toporia works unchanged.

### mmapy — Svanberg's MMA and GCMMA (`mmapy_mma`, `mmapy_gcmma`)

- **What it does.** Arjen Deetman's line-by-line Python port of Krister Svanberg's reference
  MATLAB code for the method of moving asymptotes and its globally convergent variant.
  Because it is the reference, it is the check for [`mma.py`](mma.py) (our own bisection
  solver) and for pyMOTO's MMA: three implementations that should reach the same design.
  `mmasub` is called once per outer iteration, so `mmapy_mma` is an ordinary updater on the
  [flat view](../../framework/optimisers/flat_view.py). `mmapy_gcmma` also asks the model
  for the compliance at its proposed design; if the convex approximation is not conservative
  there it stiffens it and solves again (up to 15 inner iterations per step). Those extra
  evaluations are counted in `solves`, and the last one is reused, not repeated, for the design
  adopted. `run.json` records the outer and inner iteration counts.
- **Any number of constraints**, the volume budget first (`c = 1000`, `a0 = 1`, as in the
  package's own example). One parameter, the move limit; the objective is scaled to start at 10.
- **Source and paper.** [GCMMA-MMA-Python](https://github.com/arjendeetman/GCMMA-MMA-Python)
  (PyPI `mmapy`). K. Svanberg, *IJNME* 24 (1987) 359–373; *SIAM J. Optim.* 12 (2002) 555–573.
- **Licence.** GPL-3.
- **Install.** `pip install "toporia[mmapy]"` or `pip install mmapy`.
- **Method names.** `q4+mmapy_mma`, `q4+mmapy_gcmma`, and the same with any other model
  (`h8+mmapy_mma`, `pymoto_elastic+mmapy_gcmma`, …).
- **CLI.**
  `toporia run "MBB Beam" --set method=q4+mmapy_mma --set method.move=0.2`, or both
  against our own: `toporia benchmark --methods q4+mma q4+mmapy_mma q4+mmapy_gcmma`;
  conformance: `toporia check updater:mmapy_mma updater:mmapy_gcmma`.
- **GUI.** Method stage, *Updater* picker: "MMA (mmapy)" and "GCMMA (mmapy)"; greyed out
  with the install command until the package is installed. Also listed in *Compare Methods*.
- **Measured** (MBB Beam, `m=0.4`, volume 0.5, stopping rule tol 0.01): `mmapy_mma` 274.135,
  `mma` 274.139, `pymoto_mma` 274.134, OC 274.470. `mmapy_gcmma` 274.136, with 14 inner
  iterations over 47 outer ones. With a stress limit added, the inner loop gets expensive
  (the stress aggregate is rarely conservative), which is GCMMA's nature rather than a defect
  of the adapter.

### nullspace_optimizer — Feppon's null-space method (`nullspace`)

- **What it does.** A null-space gradient flow (Feppon, Allaire & Dapogny) designed for
  level-set and shape optimisation with many constraints. Each step is the objective's
  descent direction projected onto the null space of the *active* constraints, plus a
  Gauss–Newton step that restores any that are violated or nearly active. Constraints are
  followed rather than penalised, and ones far from active are ignored. The library runs its
  own loop (`nlspace_solve`), so this is an
  [`ExternalOptimizer`](../../framework/optimisers/external_loop.py) like `scipy_slsqp`.
- **Bounds.** The library has no bound argument. Its documented route is used: the
  `bound_constraints_optimizable` decorator adds `lower − x ≤ 0` and `x − upper ≤ 0` as
  inequality constraints and clips every trial point into the box.
- **Parameters.** Time step (about the largest change of any element per iteration — it
  acts as a move limit), normalised iterations, iteration limit, tolerance. Leave
  *Normalised iterations* at its default: with a short setting the step shrinks as the gradient
  falls and the run looks converged long before it is (the engine's design-change test then
  stops it at about 460 compliance instead of 274 on the MBB beam).
- **Source and paper.** [null-space-optimizer](https://gitlab.com/florian.feppon/null-space-optimizer)
  ([documentation](https://null-space-optimizer.readthedocs.io)). F. Feppon, G. Allaire,
  C. Dapogny, "Null space gradient flows for constrained optimization with applications to
  shape optimization", *ESAIM: COCV* 26 (2020) 90.
- **Licence.** GPL-3.
- **Install.** `pip install "toporia[nullspace]"` or `pip install nullspace_optimizer`. It
  brings its own QP solvers (OSQP and others) as dependencies.
- **Method name.** `q4+nullspace` (and any other model).
- **CLI.**
  `toporia run "MBB Beam" --set method=q4+nullspace --set method.nullspace_dt=0.2`;
  conformance: `toporia check updater:nullspace`.
- **GUI.** Method stage, *Updater* picker: "Null-space optimiser", greyed out with the
  install command until installed; parameters appear beside it.
- **Measured** (MBB Beam, `m=0.4`, 200-iteration cap): compliance 274.13 against OC's 274.47.
  It does not settle under the engine's design-change test within 200 iterations, because its
  steps stay near the time step, and it makes several evaluations per iteration (line search).
  It is slower than the MMA family on this problem; its strength is constrained,
  few-variable shape problems. The library prints a harmless `fatal: not a git repository`
  to stderr when it starts: it asks git for its own revision and the install is not a checkout.

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
- L. F. N. Sivapuram, R. Picelli, "Topology optimization of binary structures using integer linear programming", *FEAD* 139 (2018) 49–61.
- R. Picelli, S. Sivapuram, Y. M. Xie, "A 101-line MATLAB code for topology optimization using binary variables and integer programming", *SMO* 63 (2021) 935–954; [doi:10.1007/s00158-020-02719-9](https://doi.org/10.1007/s00158-020-02719-9).
- O. Sigmund, "On the usefulness of non-gradient approaches in topology optimization", *SMO* 43 (2011) 589–596.
