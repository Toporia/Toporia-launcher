# Responses — what is minimised or constrained

A response is a scalar a scenario can minimise (objective) or limit (constraint), and
usually also the code that computes it and its gradient on any physics engine. See
[`core/responses.py`](../../core/responses.py).

**This is the layer where most published papers actually live.** Compliance is the easy
case — self-adjoint, one solve, no aggregation. Everything else needs its own adjoint and
usually an aggregation function (p-norm or Kreisselmeier–Steinhauser) or an augmented
Lagrangian to survive thousands of local constraints.

**Status: 3 in Toporia · 4 with open code · 14 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Declared here and computable by at least one model. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Response | File | Registry name | Role | Computable by |
| :-- | :-- | :-- | :-- | :-- |
| ✅ Compliance | [`compliance.py`](compliance.py) | `compliance` | objective | `q4`, `pymoto_elastic` |
| ✅ Material volume | [`volume.py`](volume.py) | `volume` | objective | `q4`, `pymoto_elastic` |
| ✅ Peak von Mises stress | [`stress.py`](stress.py) | `stress` | constraint | `q4`, `pymoto_elastic` |

> **What can actually enforce a constraint.** The volume *budget*
> (`scenario.volfrac`) is enforced by every method. A *second* constraint needs an updater
> that accepts one: today that is `pymoto_mma` and `pymoto_gcmma` (no limit), while
> [`oc`](../updaters/oc.py), [`mma`](../updaters/mma.py), [`simpl`](../updaters/simpl.py)
> and [`beso`](../updaters/beso.py) all declare `max_constraints = 0`. So a stress-limited
> run means pairing a model with a pyMOTO updater — `q4+pymoto_mma`. Giving Toporia's own
> updaters that ability is what the augmented Lagrangian entry below is for.

A response declares the engine features it `requires` (see
[`core/physics.py`](../../core/physics.py)); a model can offer it exactly when its engine
provides them. Compliance needs `elastic_energy`, the stress response needs `stress` — so
adding one feature to an engine adds every response built on it at once.

## Candidates — structural

| Response | Status | Reference | Why it is hard |
| :-- | :-- | :-- | :-- |
| Local stress constraints | 🔗 [PolyStress](https://link.springer.com/article/10.1007/s00158-020-02760-8) | Duysinx & Bendsøe, *IJNME* 1998; Le et al., *SMO* 2010; Giraldo-Londoño & Paulino, *SMO* 2021 | Three problems at once: the singularity phenomenon (needs ε- or qp-relaxation), local-to-global aggregation, and strong non-linearity. Augmented Lagrangian now beats global p-norm. |
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
[`core/physics.py`](../../core/physics.py), as [`compliance.py`](compliance.py) and
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
