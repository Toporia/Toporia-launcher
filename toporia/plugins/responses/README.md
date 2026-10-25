# Responses — what is minimised or constrained

A response is a scalar a scenario can minimise (objective) or limit (constraint), and
usually also the code that computes it and its gradient on any physics engine. See
[`framework/parts/response.py`](../../framework/parts/response.py).

**This is the layer where most published papers actually live.** Compliance is the easy
case — self-adjoint, one solve, no aggregation. Everything else needs its own adjoint and
usually an aggregation function (p-norm or Kreisselmeier–Steinhauser) or an augmented
Lagrangian to survive thousands of local constraints.

**Status: 4 in Toporia · 4 with open code · 14 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Declared here and computable by at least one model. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Response | File | Registry name | Role | Computable by |
| :-- | :-- | :-- | :-- | :-- |
| ✅ Compliance | [`compliance.py`](compliance.py) | `compliance` | objective | `q4`, `pymoto_elastic` |
| ✅ End compliance (non-linear) | [`end_compliance.py`](end_compliance.py) | `end_compliance` | objective | `q4_nonlinear` |
| ✅ Material volume | [`volume.py`](volume.py) | `volume` | objective | `q4`, `pymoto_elastic` |
| ✅ Peak von Mises stress | [`stress.py`](stress.py) | `stress` | constraint | `q4`, `pymoto_elastic` |
| ✅ Local von Mises stress (augmented Lagrangian) | [`local_stress.py`](local_stress.py) | `local_stress` | constraint | `q4`, `h8` |
| ✅ Thermal compliance | [`thermal_compliance.py`](thermal_compliance.py) | `thermal_compliance` | objective | `q4_heat`, `h8_heat`, `pymoto_heat` |

> **What can actually enforce a constraint.** The volume *budget*
> (`scenario.volfrac`) is enforced by every method. A *second* constraint needs an updater
> that accepts one: today that is `pymoto_mma` and `pymoto_gcmma` (no limit), while
> [`oc`](../updaters/oc.py), [`mma`](../updaters/mma.py), [`simpl`](../updaters/simpl.py)
> and [`beso`](../updaters/beso.py) all declare `max_constraints = 0`. So a stress-limited
> run means pairing a model with a pyMOTO updater — `q4+pymoto_mma`. Giving Toporia's own
> updaters that ability is what the [local stress](#local-von-mises-stress--local_stress) response and the [`augmented_lagrangian`](../updaters/README.md#augmented-lagrangian-local-constraints--augmented_lagrangian) updater are for.

**Thermal compliance** is compliance's twin for heat conduction (Bendsøe & Sigmund 2003,
section 1.5; Gersborg-Hansen et al., *SMO* 31 (2006) 251-259, [doi](https://doi.org/10.1007/s00158-005-0584-3)): C = qᵀT, the
heat input times the temperature it produces, which for uniform generation is proportional to
the mean temperature. It needs the `thermal_energy` feature, so it is offered with the heat
models only, and it is self-adjoint with a sensitivity −dk/dρ · T_eᵀK_eT_e that is never
positive: that is what lets optimality criteria (`q4_heat+oc`) minimise it. In the GUI pick a
heat model and choose it as the objective; in a scenario it is
`objective={"type": "thermal_compliance"}`.

A response declares the engine features it `requires` (see
[`framework/parts/physics.py`](../../framework/parts/physics.py)); a model can offer it exactly when its engine
provides them. Compliance needs `elastic_energy`, the stress response needs `stress` — so
adding one feature to an engine adds every response built on it at once.

## Local von Mises stress — `local_stress`

**What it does.** One stress limit *per element*, not one aggregated number. Each element has a relaxed
constraint `g = ρ^q σ_vm / limit − 1 − ε(1 − ρ) ≤ 0` (the `ρ^q` qp-relaxation, plus an optional ε slack, keeps
void elements from being "over-stressed" — the singularity phenomenon) and its own multiplier λ. The response
returns the augmented-Lagrangian penalty `P = 1/N Σ [λ h + μ/2 h²]`, `h = max(g, −λ/μ)`, with its exact gradient
from **one adjoint solve per load case**; it owns λ and μ and exposes `update_multipliers(growth)`
(`λ ← λ + μ h`, `μ ← min(growth·μ, μ_max)`), which the
[`augmented_lagrangian`](../updaters/README.md#augmented-lagrangian-local-constraints--augmented_lagrangian)
updater calls between subproblems. Its value is a penalty, not a "≤ 0 is satisfied" number: use it with that updater
only. The run reports the exact `max_stress`, `stress_ratio` and `violated_elements`, and the constraint's `exact`
value (largest `ρ^q σ_vm / limit − 1`), which the engine checks against the limit.

**When to use it.** When a single p-norm hides local overstress, e.g. the re-entrant corner of the L-bracket.
Minimise volume from a full design (volume fraction 1.0, move limit 0.05).

**How to use it.** GUI: Objective *Material volume*, add the constraint *Local von Mises stress (augmented Lagrangian)*,
updater *Augmented Lagrangian (local constraints)*; or load the preset *L-bracket (local stress)*. CLI:

```
toporia run "L-bracket (local stress)"
toporia check response:local_stress
```

**Links.** [PolyStress, SMO 63 (2021) 2065–2097](https://doi.org/10.1007/s00158-020-02760-8);
[Senhora et al., SMO 62 (2020) 1639–1668](https://doi.org/10.1007/s00158-020-02573-9).

**End compliance** is compliance for a geometrically non-linear structure: C = Σ w·fᵀu at the
final load, with the displacements from the large-displacement solve of
[`q4_nonlinear`](../models/q4_nonlinear.py) (feature `end_compliance`). It is no longer
self-adjoint, so the engine computes the sensitivity by an adjoint solve with the tangent
stiffness, K_T(u) λ = f, dC/dρₑ = −λₑᵀ ∂Rₑ/∂ρₑ — exact, and checked against finite
differences to about 1e-9. Pick it as the objective when the model is
`2-D Q4, large deformation`; the GUI offers it only there. pyMOTO has no geometrically
non-linear module, so there is no pyMOTO version.

## Candidates — structural

| Response | Status | Reference | Why it is hard |
| :-- | :-- | :-- | :-- |
| Compliant mechanisms | 📄 | Sigmund, *Mech. Struct. Mach.* 1997; Sigmund, *SMO* 2001 | Maximise output displacement against a spring. Not self-adjoint, and prone to one-node hinges that only a length-scale filter suppresses. |
| Linearised buckling | 📄 | Neves, Rodrigues & Guedes, *Comp. Struct.* 1995; Ferrari & Sigmund, *CMAME* 2019 | A generalised eigenproblem every iteration, spurious modes in low-density regions, non-differentiable repeated eigenvalues. Expensive — and the main reason compliance designs fail in reality. |
| Non-linear stability | 📄 | Dalklint, Wallin & Tortorelli, *CMAME* 2023 | Finite strain plus critical-point tracking; the tangent stiffness depends on displacement. |
| Eigenfrequency | 📄 | Díaz & Kikuchi, *IJNME* 1992; Pedersen, *SMO* 2000 | Localised modes in void regions need a mass-interpolation fix. |
| Harmonic and transient response | 🔗 PolyDyna (with the paper) | Jensen & Sigmund 2011; Giraldo-Londoño & Paulino, *SMO* 2021 | Frequency-domain or time-domain adjoints; the transient case integrates backwards over the history. |
| Fatigue and damage | 📄 | Oest & Lund, *SMO* 2017 | Load-history dependent; needs cycle counting inside the loop. |
| Fracture resistance | 📄 | Russ & Waisman, *CMAME* 2019; Da et al., *IJSS* 2021 | Phase-field fracture in the inner loop, path-dependent adjoint. |
| Design-dependent and pressure loads | 📄 | Hammer & Olhoff, *SMO* 2000; Kumar, Frouws & Langelaar, *SMO* 2020 | The load moves with the boundary. The Darcy-flow formulation is the cleanest density-based treatment. |
| Robust and reliability-based | 📄 | Sigmund, *Acta Mech. Sinica* 2009; Lazarov, Schevenels & Sigmund, *IJNME* 2012 | Uncertainty in loads, material or geometry. Worst-case, stochastic-expectation and RBTO are three formulations with very different costs. |
| Crashworthiness | 📄 | Patel, Kang & Renaud 2009 (HCA); Park, *SMO* 2011 (ESL) | Adjoints are impractical, so the field uses surrogates. Where commercial tools lead academia. |

## Candidates — other physics

| Response | Status | Reference | Note |
| :-- | :-- | :-- | :-- |
| Heat conduction | 📄 | Bendsøe & Sigmund 2003; Gersborg-Hansen, Bendsøe & Sigmund, *SMO* 2006 | Scalar field, easy adjoint. **The natural second physics to add.** |
| Thermoelasticity | 📄 | Rodrigues & Fernandes, *IJNME* 1995 | Introduces design-dependent loads. |
| Fluid flow (pressure drop) | 🔗 [TOFLUX](https://github.com/UW-ERSL/TOFLUX) | Borrvall & Petersson, *IJNMF* 2003 | Brinkman friction penalises solid inside a Stokes or Navier–Stokes solve. Over 80% of fluid TO papers use this one interpolation. |
| Conjugate heat transfer / natural convection | 📄 | Alexandersen, Aage, Andreasen & Sigmund, *IJNMF* 2014 | The highest-value industrial fluid application (heat sinks) and the most expensive. |
| Acoustics and vibro-acoustics | 📄 | Dühring, Jensen & Sigmund, *JSV* 2008 | Helmholtz problem with a solid/air interpolation; viscothermal boundary layers matter at small scales. |
| Photonic figures of merit | 🔗 [Meep](https://meep.readthedocs.io/en/latest/Python_Tutorials/Adjoint_Solver/), [ceviche](https://github.com/google/ceviche-challenges) | Jensen & Sigmund, *Laser Photonics Rev.* 2011; Christiansen & Sigmund, *JOSA B* 2021 | Permittivity as the design field; needs binarisation continuation and fabrication length scale more than mechanics does. |
| Effective material properties | 📄 | Sigmund, *IJSS* 1994 | Inverse homogenisation: design a unit cell for a target stiffness tensor, negative Poisson's ratio, and so on. Needs the unit-cell model in [`models/`](../models/README.md). |

## Adding one

A response is a declaration, and usually a computation as well: set `requires` to the
engine features it needs and implement `evaluate(state, gradient=True)` against
[`framework/parts/physics.py`](../../framework/parts/physics.py), as [`compliance.py`](compliance.py) and
[`stress.py`](stress.py) do. It is then offered by every model whose engine provides
those features. A declaration without a computation (`requires = None`) is allowed too:
only a model that computes it itself, like the pyMOTO model, will offer it, and the
capability system refuses any scenario that asks for it elsewhere, naming the methods
that can.

## References

- P. Duysinx, M. P. Bendsøe, "Topology optimization of continuum structures with local stress constraints", *IJNME* 43 (1998) 1453–1478.
- O. Giraldo-Londoño, G. H. Paulino, "PolyStress: a Matlab implementation for local stress-constrained topology optimization using the augmented Lagrangian method", *SMO* 63 (2021) 2065–2097.
- F. Ferrari, O. Sigmund, "Revisiting topology optimization with buckling constraints", *SMO* 59 (2019) 1401–1415.
- T. Borrvall, J. Petersson, "Topology optimization of fluids in Stokes flow", *IJNMF* 41 (2003) 77–107.
- R. E. Christiansen, O. Sigmund, "Inverse design in photonics by topology optimization: tutorial", *JOSA B* 38 (2021) 496–509.
