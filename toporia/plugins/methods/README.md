# Methods — how the design is described

A method owns the design variables and turns them into a density field. Most are not
written by hand: a method is named `"<model>+<updater>"` and **built on demand** from any
[model](../models/README.md) and any [updater](../updaters/README.md), so there is nothing
to declare per pairing. A method that does not split that way — the RBF level set, which
evolves its own representation with its own volume control — implements
[`framework.parts.method.OptimizationMethod`](../../framework/parts/method.py) directly.

This is the layer that decides which shapes are reachable at all. Everything below is a
different answer to "what *is* the design?".

**Status: 3 whole methods and 253 named compositions in Toporia · 10 with open code · 2 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Selectable now. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

**253 named pairings**, built from [11 models](../models/README.md) and
[23 updaters](../updaters/README.md). The available objectives and constraints are
the intersection of their capabilities. For example, `q4+oc` minimises compliance,
`q4_heat+oc` minimises thermal compliance, and `q4_buckling+pymoto_mma` can enforce
a buckling limit. Pairings with no compatible objective are rejected before solving.

**3 whole methods**, which do not split into parts:

| Method | File | Name | Reference |
| :-- | :-- | :-- | :-- |
| ✅ RBF level set | [`levelset_rbf.py`](levelset_rbf.py) | `levelset` | Wang & Wang, *CMAME* 2006 |
| ✅ Reaction-diffusion level set | [`levelset_reaction_diffusion.py`](levelset_reaction_diffusion.py) | `levelset_reaction_diffusion` | Otomori et al., *SMO* 2015; independent finite-volume variant |
| ✅ Hamilton-Jacobi level set with circular TD | [`levelset_hamilton_jacobi.py`](levelset_hamilton_jacobi.py) | `levelset_hamilton_jacobi` | Challis, *SMO* 2010; independent HJ/TD variant |

Older names are still accepted and expand through `PRESETS` in
[`__init__.py`](__init__.py): `density` → `q4+oc`, `density_mma` → `q4+mma`,
`density_simpl` → `q4+simpl`, `beso` → `q4+beso`, `density_gcmma` →
`q4+pymoto_gcmma`, `pymoto` → `pymoto_elastic+pymoto_mma`.

Covered families include **density/SIMP**, **parameterised level set** (`levelset`),
**reaction-diffusion level set** (`levelset_reaction_diffusion`), **Hamilton-Jacobi
level set with topological forcing** (`levelset_hamilton_jacobi`), and
**discrete evolutionary** (`beso`).

### Reaction-diffusion level set

This is an independent 2-D compliance implementation after
[Otomori et al. (2015)](https://doi.org/10.1007/s00158-014-1190-z), with no original
MATLAB code copied. It keeps a cell-centred field `phi` in [-1, 1]; positive is
solid. Its all-domain reaction can nucleate holes from a full-solid start and
does not use signed-distance reinitialisation or a narrow Dirac band.

The evolution is `phi_t = T / mean(abs(T)) - lambda + ell² Laplacian(phi)`.
The integrated elastic benefit `T` uses Appendix C's tensor, multiplied by the
local ersatz modulus, and sums weighted load cases. This is the paper's in-plane
reduction of its spherical-cavity tensor, **not a circular-hole asymptotic
derivative** and not the ordinary SIMP density gradient. The matrix is checked
against independent engineering-strain contractions and rigid motions.

Backward Euler and a no-flux finite-volume Laplacian give a sparse solve on the
supplied mesh; no coarsening occurs. `method.diffusion_length` is `ell` in physical
mm, whose square is the diffusion coefficient. It controls smoothing/complexity;
it does not guarantee a minimum member size. `method.dt` is the pseudo-time step.
`method.interface_width` is the dimensionless half-width of a cubic Heaviside;
outside this band cells are exactly solid/void. Inside it, stiffness is linear
in material fraction, with the scenario's `Emin` in void. Filter, interpolation
and representation plugins do not participate in this whole method.

Toporia bisects the scalar multiplier on the **new** volume rather than using
the original augmented-Lagrangian feedback. One factorisation and its response
to a constant load serve every multiplier trial; trials need no FE solves.
`method.nrelax` ramps from the initial solid volume to the budget (default 30,
0 for immediate enforcement). The engine cannot stop during that ramp. Fixed
solid/void cells impose Dirichlet values and count toward the volume. An
unreachable budget below the forced solid volume is rejected; a budget above
available material leaves all available material solid. Responses, exports and
the objective describe the same evaluated density. Change measures `max(abs(delta phi))`.

```console
python -m toporia run "MBB Beam" --set method=levelset_reaction_diffusion --set m=0.4 --set max_iter=150 --set tol=0 --set save_every=0 --out results/reaction-diffusion-validation
```

This 24×8 example reaches volume 0.5 and linear-ersatz compliance 230.917 at the
150-iteration cap. It is not a convergence claim or a like-for-like comparison
against penalised filtered OC. Mesh and smoothing choices affect the result;
oscillatory small boundary changes can persist. Springs, other objectives,
additional response constraints and 3-D are explicitly unsupported. No
bit-for-bit MATLAB reproduction or original-code oracle run is claimed.

A separate 60×20, 150-step diffusion study gives 10, 5 and 2 interior void
components for `diffusion_length` 0.5, 1 and 3 mm respectively, all at volume
0.5 (linear compliances 193.793, 190.863 and 214.989). This illustrates the
complexity control on one benchmark, not a universal monotonicity guarantee.

### Hamilton-Jacobi level set and circular-hole topological derivative

An independent implementation after [Challis (2010)](https://doi.org/10.1007/s00158-009-0430-0),
with no original MATLAB code copied. This method stores a cell-centred signed-distance
field in mm, positive inside solid (the reference uses the opposite sign). Its
binary physical density is `phi > 0`; there is no SIMP penalty on mixed cells.
The scenario's `Emin` supplies ersatz stiffness in void and is not overridden.

The evolution is `phi_t = v |grad(phi)| + omega g`. Shape velocity comes from
the compliance shape derivative; `g` is the circular-cavity derivative in cells
that were solid at the start of the update. For plane stress and a traction-free
circular hole, compliance sensitivity per removed area is
`T = (4 sigma:sigma - trace(sigma)^2)/E`. Four-point Q4 quadrature integrates this
tensor. The unit-ball factor pi multiplies both its compliance and volume terms
in the forcing, as in Challis's Eq. 13–14. This is a circular-hole asymptotic
sensitivity, not a finite SIMP density derivative. Affine-stress tests give
3/4/8 for unit uniaxial/equibiaxial/shear stress. An independent FE plate with a
small circular void approaches the uniaxial value 3 per removed area under
mesh refinement (about 3.148 to 3.101, with finite-domain/staircase errors).

Godunov upwinding selects the proper stencil for either sign of velocity.
Ten substeps per `method.step_length` cell widths give an advective CFL sum
at most 0.2, including nonsquare cells. The frozen forcing can nucleate a hole
where the signed-distance gradient is zero. Setting `method.topological_weight=0`
gives pure HJ advection. A cross-shaped `[0,1,0;1,2,1;0,1,0]/6` average smooths
the sensitivities, as in the paper; this is a heuristic velocity extension.
`method.reinitialise_every` controls EDT signed-distance resets (0 disables
them). The half-minimum-cell interface offset is exact for axis-aligned square
cells and approximate on nonsquare cells or curved boundaries. This is a
discrete ersatz method, not cut-cell FE or exact subcell geometry.

Volume uses augmented-Lagrangian feedback on the volume **fraction**, with
initial multiplier -0.01 and penalty denominator 1000, decayed by 0.9 per step.
Toporia normalises cell energy by its initial mean, equivalent to normalising
the objective by initial compliance; force/material units therefore cancel in
the evolution. The penalty denominator has a 1e-6 floor. Material cells touching
supports or applied forces stay solid and count toward volume, in addition to
the user's fixed regions. Force-bearing cells cannot overlap forced void.
An insufficient budget is rejected. The target is rounded down to an integer
number of cells and capped at available material, so its quantisation never
increases the requested budget.

The method's stopping criterion requires feasible volume within
`method.volume_tolerance` below that target and compliance stable against five
previous values within `method.objective_tolerance`. Default tolerances are
0.005 and 0.01. The engine cannot stop early while volume lies outside that
band. Parameters, discretisation and the volume controller can still produce
oscillations or poor local minima on other problems; reaching the iteration cap
does not establish feasibility or convergence. The result reports both.

```console
python -m toporia run "MBB Beam" --set method=levelset_hamilton_jacobi --set m=0.4 --set max_iter=200 --set tol=0 --set save_every=0 --out results/hamilton-jacobi-validation
```

This 24×8 run meets the joint criterion after 86 updates: compliance 246.108358,
volume 0.5. The 60×20 run settles after 110 updates: compliance 191.667832,
volume 0.5. Both pass an actual same-mesh filtered-OC comparison within the
unchanged 10% quality allowance. All density values are binary; FE responses
and exports describe the same design. Extra force/support protection differs
from the density model's unrestricted design space. Springs, other objectives,
additional response constraints and 3-D are unsupported. Generalised two-phase
topological-gradient optimisers (e.g. Amstutz–Andrä's geodesic algorithm) remain
distinct candidates; this implementation supplies Challis's HJ/cavity combination.

## Candidates — density and discrete

| Family | Status | Reference | What it adds |
| :-- | :-- | :-- | :-- |
| Homogenisation | 📄 | Bendsøe & Kikuchi, *CMAME* 1988 | The original formulation: microstructure density and orientation as variables. Now mainly a route into multiscale work. |
| TOBS — binary + integer programming | 🔗 [101-line MATLAB](https://link.springer.com/article/10.1007/s00158-020-02719-9) | Sivapuram & Picelli 2018; Picelli et al., *SMO* 2021 | Strictly {0,1} variables with several constraints handled explicitly. Needs the ILP updater in [`updaters/`](../updaters/README.md). |
| Multi-material | 🔗 [PolyMat](https://dl.acm.org/doi/abs/10.1007/s00158-018-2094-0) | Stegmann & Lund 2005 (DMO); Tavakoli & Mohseni, *SMO* 2014; Zuo & Saitou, *SMO* 2017 (ordered SIMP) | Three competing schemes: ordered SIMP (one variable, cost-scaled), DMO/SFP (one variable per material), alternating active phase (a sequence of two-phase problems). |
| Multiscale, lattice infill, de-homogenisation | 🔗 [MultiscaleTopOpt](https://github.com/LLNL/MultiscaleTopOpt) | Groen & Sigmund, *IJNME* 2018; Groen et al., *CMAME* 2020; review: Wu, Sigmund & Groen, *SMO* 2021 | Optimise a coarse density-and-orientation field with homogenised properties, then project it to a fine single-scale structure. Three orders of magnitude cheaper than resolving the lattice. Related: shell/coating (Clausen et al. 2015), bone-like infill (Wu et al. 2018). |

## Candidates — level set and implicit

| Family | Status | Reference | What it adds |
| :-- | :-- | :-- | :-- |
| Generalised topological-gradient optimiser | 🔗 [FreeFEM code](https://link.springer.com/article/10.1007/s00158-023-03529-5) | Sokołowski & Żochowski, *SICON* 1999; Amstutz & Andrä, *JCP* 2006; Novotny et al., *SMO* 2023 | Standalone two-phase/reinforcement schemes. The circular-hole derivative is already implemented and physically checked in `levelset_hamilton_jacobi`. |
| Phase field | 📄 | Bourdin & Chambolle, *ESAIM:COCV* 2003; Takezawa, Nishiwaki & Kitamura, *JCP* 2010 | Cahn–Hilliard / Allen–Cahn energy with a double-well potential: the perimeter penalty is intrinsic, so **no filter is needed at all**. Couples naturally to phase-field fracture. |

## Candidates — explicit geometry

Explicit bars and projected geometric features (moving morphable components, geometry
projection) are not whole methods any more: they are
[design representations](../representations/README.md), and run through the same model
and updaters as element densities. Moving morphable components are in Toporia.

| Family | Status | Reference | What it adds |
| :-- | :-- | :-- | :-- |
| Ground structure / truss layout | 🔗 [GRAND, GRAND3](https://paulino.princeton.edu/journal_papers/2014/SMO_14_GRAND.pdf) | Michell 1904; Zegard & Paulino, *SMO* 2014, 2015; He, Gilbert et al., *SMO* 2019 | A dense candidate bar network sized by LP/NLP. **A genuinely different design space from a density field**, converging to Michell layouts; the natural formulation for frames. |
| Isogeometric TO | 🔗 IgaTop (with the paper) | Gao et al. (IgaTop) | NURBS basis shared by geometry, analysis and density: no re-meshing, smooth boundaries straight into CAD. |
| Stiffness spreading | 🔗 [SSM](https://github.com/PengWeiScut/SSM) | Wei et al. 2010 | Explicit-geometry precursor to the projection methods above. |

## Candidates — learned parameterisations

Three genuinely different things, which fail in different ways. Only the first belongs in
this folder; the other two are listed in [`models/`](../models/README.md) and for context.

| Family | Status | Reference | What it adds |
| :-- | :-- | :-- | :-- |
| Neural reparameterisation | 🔗 [TOuNN](http://www.ersl.wisc.edu/software/TOuNN.zip) | Hoyer, Sohl-Dickstein & Greydanus 2019; Chandrasekhar & Suresh, *SMO* 2021; Jain & Suresh, *Eng. Comput.* 2023 (DMF-TONN) | The density field **is** a network: weights are the design variables, the FE solver stays in the loop, no training data, and the result is still physically feasible. Mesh-independent and resolution-free. The safest learned method to add, and it needs the Adam updater. |
| Direct generation (GAN, diffusion) | 🔗 [nn4topopt](https://github.com/ISosnovik/nn4topopt), [dl4to](https://github.com/dl4to/dl4to) | Sosnovik & Oseledets 2019; Nie et al., *JMD* 2021 (TopologyGAN); Mazé & Ahmed, *AAAI* 2023 (TopoDiff) | Maps boundary conditions straight to a structure. Fast and genuinely multi-candidate — what "generative design" promises — but constraint satisfaction and out-of-distribution behaviour are unsolved. Needs a trained model and the datasets in [`problems/`](../problems/README.md). |
| Online surrogate | 🔗 [SOLO](https://github.com/deng-cy/deep_learning_topology_opt) | Deng et al. 2022 | Trains the surrogate during the optimisation instead of on a pre-built dataset. |

## References

- M. P. Bendsøe, O. Sigmund, *Topology Optimization: Theory, Methods and Applications*, Springer 2003.
- O. Sigmund, K. Maute, "Topology optimization approaches: a comparative review", *SMO* 48 (2013) 1031–1055.
- J. D. Deaton, R. V. Grandhi, "A survey of structural and multidisciplinary continuum topology optimization", *SMO* 49 (2014) 1–38.
- S. Wein, P. D. Dunning, J. A. Norato, "A review on feature-mapping methods for structural optimization", *SMO* 62 (2020) 1597–1638.
- X. Huang, "Open-source codes of topology optimization: a summary for beginners", *CMES* 137 (2023) — the survey these tables were built from.
