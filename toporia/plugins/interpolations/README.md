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

**Status: 3 in Toporia · 0 with open code · 3 paper only**

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
| ✅ Ordered SIMP | [`ordered_simp.py`](ordered_simp.py) | `ordered_simp` | piecewise t^p between ordered materials | Zuo & Saitou, *SMO* 2017 |

RAMP's slope at ρ = 0 is (E0 − Emin)/(1 + q), where SIMP's is zero: a void element still
feels a sensitivity, which design-dependent loads (pressure, self-weight) need. Compare
the two on any problem with **Compare Two** on `interpolation.type`, or by running one
method with each law.

## 📄 Candidates

| Law | Reference | What it adds |
| :-- | :-- | :-- |
| 📄 SINH (needs a framework change: the volume response must take a law, see below) | Bruns, *SMO* 30 (2005) 428–436 | Penalises the *volume* instead of the stiffness (a sinh law on the density), with consequences for filtering and for what counts as solid. |
| 📄 Hashin–Shtrikman-bound laws (needs ν, which the interface does not receive, see below) | Bendsøe & Sigmund, *Arch. Appl. Mech.* 69 (1999) 635–654 | Shows when a power law corresponds to a physically realisable composite (p large enough for the Poisson's ratio); the bounds themselves as an interpolation. |
| 📄 Discrete material optimisation (DMO) | Stegmann & Lund, *IJNME* 62 (2005) 2009–2027 | Several candidate materials per element, each with its own weight: the classic multi-material law. Needs one design variable per material — a design representation with several fields. |

## Ordered SIMP

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

Paper: W. Zuo, K. Saitou, *SMO* 55 (2017) 477–491, [doi:10.1007/s00158-016-1513-3](https://doi.org/10.1007/s00158-016-1513-3).

Use it: `"interpolation": {"type": "ordered_simp", "n_materials": 3, "rho2": 0.5, "E2": 0.3}`
in the solver JSON, the **Material law** picker in the GUI, or

```
toporia run "MBB Beam" --set method=q4+oc --set interpolation.type=ordered_simp --set interpolation.n_materials=3
```

## Not done, and why

- **SINH** (Bruns, *SMO* 30 (2005) 428–436, [doi:10.1007/s00158-005-0543-3](https://doi.org/10.1007/s00158-005-0543-3)):
  it penalises the *volume* (mass) with a sinh law while stiffness stays linear. An
  `Interpolation` only maps ρ to stiffness, and the volume response measures Σρ without
  asking any law. Implementing "stiffness linear" alone would be SIMP with p = 1, not SINH,
  so it is left out until the volume response can take an interpolation.
- **Hashin–Shtrikman bound law** (Bendsøe & Sigmund, *Arch. Appl. Mech.* 69 (1999) 635–654,
  [doi:10.1007/s004190050248](https://doi.org/10.1007/s004190050248)): the bound depends on
  Poisson's ratio ν, but `stiffness(density, E0, Emin)` receives only E0 and Emin, not the
  scenario's material. Making ν reachable is a framework change.

## Writing one

Subclass `Interpolation`, give it `name`, `label` and `params` (the constructor takes each
as a keyword), and implement `stiffness(density, E0, Emin)` and
`slope(density, E0, Emin)`, element-wise on arrays of any shape. Then
`toporia check interpolation:<name>`: it checks E(0) = Emin, E(1) = E0, that E increases,
the slope against finite differences, and a short run.

## References

- M. P. Bendsøe, "Optimal shape design as a material distribution problem", *Structural Optimization* 1 (1989) 193–202.
- M. Stolpe, K. Svanberg, "An alternative interpolation scheme for minimum compliance topology optimization", *SMO* 22 (2001) 116–124.
- M. P. Bendsøe, O. Sigmund, "Material interpolation schemes in topology optimization", *Archive of Applied Mechanics* 69 (1999) 635–654.
