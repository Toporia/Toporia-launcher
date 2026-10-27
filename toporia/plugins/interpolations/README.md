# Material laws — how density becomes stiffness

A density method needs a material law for intermediate densities: an interpolation
between void (`Emin`) and solid (`E0`),

```
E(ρ) = Emin + f(ρ) · (E0 − Emin),      f(0) = 0,  f(1) = 1,
```

shaped so that grey material is not worth its cost and the optimum is driven towards
black and white. The law is a part of its own — see
[`framework/parts/interpolation.py`](../../framework/parts/interpolation.py) — chosen in the
solver like the filters, `solver.interpolation = {"type": "ramp", "q": 8}`, and shown in
the GUI's **Material law** panel. Any physics engine that declares `uses_interpolation`
(the Q4 engine does) takes it; models that bring their own (pyMOTO) or none (the level
set) ignore it, and the Pipeline box says so.

**Status: 5 in Toporia · 0 with open code · 1 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here, registered, passes `toporia check interpolation:<name>`. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Law | File | Name | f(ρ) | Reference |
| :-- | :-- | :-- | :-- | :-- |
| ✅ SIMP | [`simp.py`](simp.py) | `simp` | ρ^p (p = 3) | Bendsøe, *Struct. Optim.* 1989 |
| ✅ RAMP | [`ramp.py`](ramp.py) | `ramp` | ρ / (1 + q(1 − ρ)) (q = 8) | Stolpe & Svanberg, *SMO* 2001 |
| ✅ Ordered SIMP, interval-local variant | [`ordered_simp.py`](ordered_simp.py) | `ordered_simp` | piecewise t^p between ordered materials | da Silveira & Palma 2022 modified law, increasing-modulus branch; inspired by Zuo & Saitou 2017 |
| ✅ Basic SINH, shared-density variant | [`sinh.py`](sinh.py) | `sinh` | linear stiffness; effective volume `1-sinh(p(1-rho))/sinh(p)` | Bruns, *SMO* 2005, Table 2 case 5 |
| ✅ Hashin-Shtrikman fixed-nu upper envelope | [`hashin_shtrikman.py`](hashin_shtrikman.py) | `hashin_shtrikman` | stricter elastic bulk/shear upper limit, at scenario nu | Bendsøe & Sigmund 1999; finite soft phase included |

RAMP's slope at ρ = 0 is (E0 − Emin)/(1 + q), where SIMP's is zero: a void element still
feels a sensitivity, which design-dependent loads (pressure, self-weight) need. Compare
the two on any problem with **Compare Two** on `interpolation.type`, or by running one
method with each law.

## 📄 Candidates

| Law | Reference | What it adds |
| :-- | :-- | :-- |
| 📄 Discrete material optimisation (DMO) | Stegmann & Lund, *IJNME* 62 (2005) 2009–2027 | Several candidate materials per element, each with its own weight: the classic multi-material law. Needs one design variable per material — a design representation with several fields. |

## Ordered SIMP

The [Batch 2 source audit](../../../docs/research/batch-2.md) distinguishes the
implemented interval-local expression below from the original 2017
`A*rho**p+B` equation. It matches the increasing-modulus branch of
[da Silveira & Palma (2022), equations 4-6 and Figure 1](https://doi.org/10.1007/s00158-022-03379-7).
The reference metadata is corrected; numerical behavior is unchanged.

```
t = (ρ − ρ_i) / (ρ_{i+1} − ρ_i),    E(ρ) = Emin + [f_i + t^p (f_{i+1} − f_i)] (E0 − Emin)
```

for ρ between the densities ρ_i and ρ_{i+1} of two neighbouring materials, whose moduli
(fractions of E0) are f_i and f_{i+1}. The materials are void (0, 0), up to two grey ones
and the solid (1, 1). One variable per element runs through all of them, and for p > 1
the stiffness is flat just above each material's density, so the optimiser settles on
one of the materials rather than in between. With 2 materials it is plain SIMP. Defaults:
densities 0 / 0.4 / 0.7 / 1 with moduli 0 / 0.25 / 0.55 / 1.
**Use it** for multi-material or graded-density designs with a single field.

**Not included:** the paper's cost side (each material has a cost and the *interpolated cost*
is constrained). Toporia's volume response constrains Σρ, so the constraint is on the mass
fraction implied by the densities; a per-material cost would need the volume response to
accept an interpolation, which is a framework change.

Original inspiration: W. Zuo, K. Saitou, *SMO* 55 (2017) 477–491,
[doi:10.1007/s00158-016-1513-3](https://doi.org/10.1007/s00158-016-1513-3).
That original formula is plotted separately in the reproduction audit.

Use it: `"interpolation": {"type": "ordered_simp", "n_materials": 3, "rho2": 0.5, "E2": 0.3}`
in the solver JSON, the **Material law** picker in the GUI, or

```
toporia run "MBB Beam" --set method=q4+oc --set interpolation.type=ordered_simp --set interpolation.n_materials=3
```

## SINH: effective volume rather than stiffness penalisation

Bruns' [equations 22-23](https://doi.org/10.1007/s00158-005-0537-x) define
`eta1=rho`, `eta2=1-sinh(p*(1-rho))/sinh(p)`. Stiffness is linear between Emin
and E0, while the budget constrains `sum(eta2)`, whose derivative is
`p*cosh(p*(1-rho))/sinh(p)`. The p=0 limit is linear stiffness and volume.
`p` defaults to 3 and is schedulable as `interpolation.penal`.

The implemented shared-density variant uses the same filtered field in both
measures: Table 2 case 5 with a density filter, case 4 without filters. The
paper's basic case 6 filters only the resource field; that separate-filter
formulation and hybrid SINH are not included. Shared filtering can retain diffuse
gray boundaries. No claim is made to reproduce the paper's case-6 topologies.

The interpolation interface now supplies `volume_density` and `volume_slope`,
with identity defaults preserving existing laws. Assembled models apply the
selected cost to evaluation, cheap updater bisections and volume objectives,
and carry its derivative through the filters and representation. Element-density
starts are calibrated to the effective budget. Passive solids cost one and voids
cost zero. Other representations may start over budget and rely on the updater.

Geometric density remains the displayed field and the usual `volume` history/
study column. `effective_volume_fraction` is reported on the actual current
design; limit checks use it and label the effective budget explicitly. Compare
Methods adds `effective_volume` and keeps the common SIMP p=3 referee. SINH's
linear-stiffness objective and that referee measure different material models.
Intermediate effective cost is not true geometric volume, mass or a certified
homogenised composite. Smooth and binary volumes coincide only at 0/1.

```sh
toporia run "MBB Beam" --set method=q4+mma --set interpolation.type=sinh --set interpolation.penal=3 --set method.move=0.05 --set max_iter=300 --set tol=0
```

GUI: choose **SINH (linear stiffness, penalised volume)** in Material law.
`python -m experiments.material_laws` prints bounded fresh final checks; see
[measured results](../../../experiments/README.md#sinh-effective-volume).

## Hashin-Shtrikman: fixed-nu upper envelope

The law receives the scenario's actual Poisson ratio and dimension through
`setup(problem)`; default laws retain a no-op setup. It takes the stricter of
the HS bulk and shear upper bounds along the solver's fixed-nu elastic ray.
For either channel M, with solid modulus M0 and soft modulus Mmin,

```
q_M = (M0-Mmin)/(Mmin+a_M)
q = max(q_bulk, q_shear)
E(rho) = Emin + (E0-Emin)*rho/(1+q*(1-rho))
```

For plane stress, `k=E/[2(1-nu)]`, `g=E/[2(1+nu)]`, `a_k=g`,
`a_g=k*g/(k+2*g)`. In 3-D, `k=E/[3(1-2*nu)]`, `a_k=4*g/3`,
`a_g=g*(9*k+8*g)/(6*(k+2*g))`. Shifts use the solid phase. Both phases share
nu; Emin participates in the bound, rather than being added to a void-limit law.
The derivative is analytic and nonzero at void for positive stiffness contrast.
The volume measure stays geometric. There is no independent penalty knob.

This is an **upper envelope with fixed nu**, not the density-dependent nu of
[Bendsøe & Sigmund eq.17](https://doi.org/10.1007/s004190050248). Only at
plane-stress nu=1/3 and Emin=0 does it reduce to their `E0*rho/(3-2*rho)`
while preserving nu. It satisfies both upper-channel limits; it does not assert
the lower bounds, joint attainability or a realisable microstructure. In particular,
finite soft phases and extreme nu can make a fixed-nu tensor fall outside a lower
channel bound. Variable-nu constitutive tensors and arbitrary phase Poisson ratios
remain separate work. Underlying element limitations also remain.

Only mechanical engines are supported. A thermal model is refused in preflight
with an explanation; elastic HS limits are not conductivity limits. In direct
Python use, call `law.setup(problem)` before passing it to a physics engine.
The accepted solid range is `-1 < nu < 0.5`, with `0 <= Emin <= E0`, E0 positive.

GUI: choose **Hashin-Shtrikman upper envelope (fixed nu)**. CLI:

```sh
toporia run "MBB Beam" --set method=q4+mma --set interpolation.type=hashin_shtrikman --set method.move=0.05 --set max_iter=300 --set tol=0
```

`python -m experiments.material_laws --law hashin_shtrikman` prints fresh final
benchmarks. Independent reciprocal-form checks cover six nu values, five phase
contrasts and both dimensions; physical compliance gradients also pass.
The [3-D bound formula source](https://sepwww.stanford.edu/sep/berryman/PS/PHYS.pdf)
and [benchmark notes](../../../experiments/README.md#hashin-shtrikman-upper-envelope)
give context and measured limits.

## Writing one

Subclass `Interpolation`, give it `name`, `label` and `params` (the constructor takes each
as a keyword), and implement `stiffness(density, E0, Emin)` and
`slope(density, E0, Emin)`, element-wise on arrays of any shape. Then
`toporia check interpolation:<name>`: it checks E(0) = Emin, E(1) = E0, that E increases,
the slope against finite differences, and a short run.
Optional `setup(problem)` binds scenario context and `problems_with(physics)`
declares restrictions shared by GUI/study preflight and model initialisation.
Optional volume hooks provide an effective resource cost and its derivative;
set `nonlinear_volume=True` when that budget differs from geometric density.

## References

- M. P. Bendsøe, "Optimal shape design as a material distribution problem", *Structural Optimization* 1 (1989) 193–202.
- M. Stolpe, K. Svanberg, "An alternative interpolation scheme for minimum compliance topology optimization", *SMO* 22 (2001) 116–124.
- M. P. Bendsøe, O. Sigmund, "Material interpolation schemes in topology optimization", *Archive of Applied Mechanics* 69 (1999) 635–654.
