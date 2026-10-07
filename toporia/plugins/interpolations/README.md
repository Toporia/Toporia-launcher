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

**Status: 2 in Toporia · 0 with open code · 4 paper only**

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

RAMP's slope at ρ = 0 is (E0 − Emin)/(1 + q), where SIMP's is zero: a void element still
feels a sensitivity, which design-dependent loads (pressure, self-weight) need. Compare
the two on any problem with **Compare Two** on `interpolation.type`, or by running one
method with each law.

## 📄 Candidates

| Law | Reference | What it adds |
| :-- | :-- | :-- |
| 📄 SINH | Bruns, *SMO* 30 (2005) 428–436 | Penalises the *volume* instead of the stiffness (a sinh law on the density), with consequences for filtering and for what counts as solid. |
| 📄 Hashin–Shtrikman-bound laws | Bendsøe & Sigmund, *Arch. Appl. Mech.* 69 (1999) 635–654 | Shows when a power law corresponds to a physically realisable composite (p large enough for the Poisson's ratio); the bounds themselves as an interpolation. |
| 📄 Discrete material optimisation (DMO) | Stegmann & Lund, *IJNME* 62 (2005) 2009–2027 | Several candidate materials per element, each with its own weight: the classic multi-material law. Needs one design variable per material — a design representation with several fields. |
| 📄 Ordered SIMP | Zuo & Saitou, *SMO* 55 (2017) 477–491 | Multi-material with a single variable per element, piecewise between ordered materials scaled by cost. Fits this interface directly. |

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
