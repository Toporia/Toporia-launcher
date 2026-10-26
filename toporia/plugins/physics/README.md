# Finite elements — discretisation

The element formulation and the assemble-and-solve routine a model uses. Kept separate
from [`models/`](../models/README.md) because the same physics can be discretised many
ways, and the choice of element is itself a thing worth comparing: it decides what the
density field can resolve and where the classic numerical artefacts come from.

**Status: 9 in Toporia · 5 with open code · 3 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Element | File | Scope |
| :-- | :-- | :-- |
| ✅ Q4 plane stress | [`q4_plane_stress.py`](q4_plane_stress.py) | Bilinear quadrilateral, 2 DOF per node, structured grid, column-major numbering, analytic element stiffness. The top88 element. 2-D. |
| ✅ Nested multiresolution Q4 | [`q4_multiresolution.py`](q4_multiresolution.py) | Fine-cell material integrated exactly into a coarse displacement space. Full fine-density energy gradient, virtual-work-preserving loads and fine-grid support constraints. 2-D elastic energy only. |
| ✅ Q4 port springs and probes | [`q4_mechanism.py`](q4_mechanism.py) | Separate subclass with density-independent springs, signed point probes and one shared state/adjoint LU. External work includes spring energy. Adds the `point_displacement` feature; 2-D small-displacement elasticity. |
| ✅ Q4 linearised buckling | [`q4_buckling.py`](q4_buckling.py) | Static Q4 plus geometric stiffness, positive buckling factors and the adjoint sensitivity through the prebuckling displacement. 2-D. |
| ✅ Q4 large deformation | [`q4_nonlinear.py`](q4_nonlinear.py) | The same Q4 element with geometric non-linearity: total Lagrangian, Green–Lagrange strain, St Venant–Kirchhoff material, 2 × 2 Gauss, internal force and tangent stiffness per element, Newton–Raphson with load steps (halved automatically where Newton struggles). Provides `end_compliance`. 2-D. |
| ✅ H8 solid | [`h8_solid.py`](h8_solid.py) | Trilinear brick, 3 DOF per node, 2 × 2 × 2 Gauss integration, the element of Liu & Tovar's top3d. 3-D: a scenario with a depth `Lz`. Direct sparse solver, or conjugate gradients with algebraic multigrid (optional `pyamg`) for large meshes. |
| ✅ Q4 heat conduction | [`q4_heat.py`](q4_heat.py) | Bilinear quadrilateral, 1 temperature per node, same grid and element numbering as the Q4 plane-stress element. Steady conduction with uniform heat generation; supports are heat sinks. 2-D. |
| ✅ H8 heat conduction | [`h8_heat.py`](h8_heat.py) | Trilinear brick, 1 temperature per node, 2 × 2 × 2 Gauss integration. The 3-D counterpart of `q4_heat`, for a scenario with a depth `Lz`. |
| ✅ Q4 with vibration | [`q4_dynamic.py`](q4_dynamic.py) | The Q4 plane-stress engine plus a mass matrix (consistent or lumped, Pedersen's low-density fix, optional non-structural mass at the load nodes). Adds the features `modes` (eigenvalues of `K φ = λ M φ` by shift-invert ARPACK, with their sensitivities) and `harmonic` (`(K − ω²M) u = f`, dynamic compliance and its adjoint). 2-D. |

Each module is a [`framework.parts.physics.Physics`](../../framework/parts/physics.py) engine:
it solves a density to a state and declares which features it answers (`elastic_energy`,
`stress`, and for vibration `modes` and `harmonic`) and in which dimensions (`dims`). Adding an element formulation below means
implementing that interface, after which every response and filter in the library that
works in its dimension applies to it unchanged.

**How H8 is checked.** With Poisson's ratio 0, a design that does not vary through the depth
must behave exactly as the 2-D design in plane stress. Its 3-D compliance is then the Q4
compliance divided by the depth, which holds to 1e-12 on the cantilever, the MBB beam and
the drone arm (holes and solid rings included). A test asserts it in
`tests/plugins/test_3d.py`. The finite-difference gradient checks of `toporia check
model:h8` and `toporia check response:stress` cover its compliance and 3-D stress
sensitivities.

### Multiresolution analysis

For an integer subdivision factor, let `P` interpolate coarse Q4 nodal
displacements to the nested fine grid. Every coarse bilinear function is
represented exactly on each fine cell. The implementation assembles
`K_c = P.T @ K_f(rho) @ P`; this is 2×2 Gauss integration of the coarse
strain field over each constant-density fine cell. Only the coarse system is
solved. Fine strain energies give `dC/drho_i = -E'(rho_i) * u_i.T @ KE_i @ u_i`.
The material law, fine density, filters and volume response remain independent.

Fine loads transfer as `P.T @ f`, preserving virtual work. Fine Dirichlet
conditions become `C @ u_c = 0`. Unit constraints are eliminated; rank-revealing
QR removes redundant remaining conditions before a sparse saddle-system solve.
This retains fine-grid point/ring supports instead of moving them. The original
Q4 source is unchanged, and factor 1 delegates directly to it.

This is an independently derived aligned 2-D MTOP variant, not the full
three-mesh/adaptive/higher-order formulations. The
[model documentation](../models/README.md#multiresolution-q4_multiresolution)
describes supported cases and why independent fine reevaluation is essential.
Tests include independent Gauss integration of nonuniform subcell material,
coarse-Q4 equivalence for uniform material, bilinear interpolation, virtual work,
projected point/ring supports, full gradients and a disconnected-strip artefact.

### Heat conduction

Steady heat conduction, −∇·(k∇T) = Q, discretised with one temperature per node
(Bendsøe & Sigmund 2003, section 1.5; Gersborg-Hansen, Bendsøe & Sigmund, *SMO* 31 (2006)
251-259, [doi](https://doi.org/10.1007/s00158-005-0584-3)). It is the first engine whose `provides` is not the structural
pair: it answers the `thermal_energy` feature (`thermal_compliance`, `thermal_energy`), and
the shared assembly and solve live in [`_conduction.py`](_conduction.py). A scenario means
the same geometry with another meaning:

| Scenario | Heat conduction |
| :-- | :-- |
| supports (edge or point constraints, any `dof`) | fixed temperature T = 0, heat sinks |
| point loads and load holes | heat input; only the load case's `Fmag` is used, its direction means nothing |
| `E0`, `Emin` | conductivity of solid and of void |
| physics parameter `heat_source` | uniform generation over the whole domain (default 1e-4 per mm², so q·L² = 1 on a 100 mm plate) |

The heat input does not depend on the density, so the thermal compliance qᵀT is self-adjoint
and its sensitivity −dk/dρ · T_eᵀK_eT_e needs no extra solve. The strip test in
`tests/plugins/test_heat.py` reproduces the analytic maximum temperature Q L²/8k to 1e-10,
in 2-D and in 3-D.

### Large deformation (`q4_nonlinear`)

**What.** Large displacements and rotations with small strains. The equilibrium is written
on the deformed shape: F = I + ∇u, Green–Lagrange strain E = ½(FᵀF − I), second
Piola–Kirchhoff stress S = D·E (St Venant–Kirchhoff: the linear plane-stress law on the
Green strain). The element internal force and tangent stiffness (material part plus the
initial-stress part) are formed per element with 2 × 2 Gauss points; the tangent is checked
against differences of the force. A load is applied in `steps` increments, each solved by
Newton–Raphson with a backtracking line search; an increment Newton cannot follow is halved,
and if it still fails the solve stops with an error that says at which load fraction. A
design that snaps or buckles under the load (a limit point) cannot be followed in load
control — lower the load or the move limit.

**Low-density elements.** Void distorts under its neighbours' displacements and stalls
Newton. The remedy is an *energy interpolation*, after Wang, Lazarov, Sigmund & Jensen,
"Interpolation scheme for fictitious domain techniques and topology optimization of finite
strain elastic problems", *CMAME* 276 (2014) 453-472
([doi](https://doi.org/10.1016/j.cma.2014.03.021)): the element energy is
E(ρ)·[(1 − s(ρ))·ψ<sub>nonlinear</sub> + s(ρ)·ψ<sub>linear</sub>], where s is a smoothstep that is 1 below
`linear_below` and 0 above `linear_above` (defaults 0.1 and 0.2). Void is then a constant
linear spring and cannot invert, while material is fully non-linear. This is Toporia's
formulation of that principle, not the paper's exact switching function. The simpler remedy
of Buhl, Pedersen & Sigmund, *SMO* 19 (2000) 93-104
([doi](https://doi.org/10.1007/s001580050089)) — relaxing the convergence test in void
elements — is not used. The open reference is the 137-line code of Han et al., *SMO* 63
(2021) ([doi](https://doi.org/10.1007/s00158-020-02816-9)).

**Sensitivity.** For the end compliance C = fᵀu the engine solves the adjoint system
K<sub>T</sub>(u) λ = f once per load case and returns dC/dρₑ = −λₑᵀ ∂Rₑ/∂ρₑ, exactly
(including the derivative of the energy blend). It is not minus an element energy any
more. **pyMOTO has no geometrically non-linear module, so there is no pyMOTO version.**

**In the GUI.** The physics picker is the model picker: choose *2-D Q4, large deformation
(Toporia)*; it offers *End compliance (non-linear)* as the objective, and the Newton
parameters (load steps, tolerance, iterations, linear/non-linear density band) appear
with the model's settings. **On the command line** see the *Nonlinear Cantilever* preset
in [`problems/`](../problems/README.md).

## Vibration: eigenfrequencies and harmonic response

`q4_dynamic.py` subclasses the static engine (which is untouched, so its results stay
bit-identical) and adds a mass matrix. Element mass is `m(ρ) · M_e` with `m(ρ) = ρ` above a
threshold ρc and `ρc (ρ/ρc)^r` below it (ρc = 0.1, r = 6 by default). Without that, void
elements have stiffness `ρ³` but mass `ρ`, so the lowest "modes" are spurious oscillations of
the void (Pedersen 2000; Du & Olhoff 2007). Set `low_density_below` to 0 to switch the fix
off and get the plain linear mass. The mass density, a consistent or lumped mass matrix and a
non-structural `attached_mass` (shared by the load nodes, so a payload is just a point load
that also weighs something) are parameters of the model.

- **Free vibration**: `K φ = λ M φ`, `λ = ω²`, modes normalised to `φᵀ M φ = 1`, sensitivity
  `dλ/dρ_e = φ_eᵀ (dE/dρ_e K_e − λ dm/dρ_e M_e) φ_e`. Valid for a simple eigenvalue; the
  [`eigenfrequency`](../responses/eigenfrequency.py) response aggregates several eigenvalues
  to handle repeated ones.
- **Forced vibration**: `(K − ω² M) u = f`, dynamic compliance `fᵀu`, self-adjoint sensitivity
  `−u_eᵀ (dE/dρ_e K_e − ω² dm/dρ_e M_e) u_e`.

**How it is checked.** The first bending frequency of a slender cantilever agrees with
Euler–Bernoulli beam theory to 1.4 % at 4 elements per depth; the lowest three eigenvalues
agree with pyMOTO's own `AssembleMass` and `EigenSolve` ([`pymoto_dynamic.py`](../models/pymoto_dynamic.py))
to 1e-13 relative on the same density; the sensitivities match finite differences; the mass
fix is shown to remove the void modes. All in `tests/plugins/test_dynamics.py`.

Papers: Díaz & Kikuchi, *IJNME* 35 (1992) 1487–1502 ([doi](https://doi.org/10.1002/nme.1620350707));
Pedersen, *SMO* 20 (2000) 2–11 ([doi](https://doi.org/10.1007/s001580050130));
Du & Olhoff, *SMO* 34 (2007) 91–110 ([doi](https://doi.org/10.1007/s00158-007-0101-y)).

Two consequences worth knowing before adding anything here:

- **The material law is a part of its own.** The engine declares `uses_interpolation`, so
  SIMP, RAMP or any law in [`interpolations/`](../interpolations/README.md) can be chosen
  in the solver; it no longer has a `penal` of its own.
- **Q4 under-integrates bending and produces checkerboards**, which is the historical
  reason the filters in [`filters/`](../filters/README.md) exist at all. A higher-order or
  mixed element changes that story, so "which element" is a legitimate comparison axis and
  not an implementation detail.

### Linearised buckling

`q4_buckling` subclasses the unchanged static engine. It forms the initial-stress
stiffness from centroid stresses and 2 × 2 Gauss integration, then solves
`(-K_σ) φ = μ K φ`, with `λ = 1/μ` the positive load multiplier. The density
exponent `p_sigma` (default 4) suppresses geometric stiffness in void. The
sensitivity includes both explicit stiffness terms and an adjoint through `K u = f`.
The implementation follows the formulation of [Ferrari, Sigmund & Guest (2021)](https://doi.org/10.1007/s00158-021-02854-x);
the response uses a p-norm rather than the paper's KS aggregation.

Select *2-D Q4 with buckling (Toporia)* in the GUI, or load *Column Buckling*.
CLI example: `toporia run "Column Buckling" --set m=0.3 --set max_iter=120`.
Tests check Euler's cantilever-column load, finite differences including the
adjoint, tension, physical-unit scaling, and agreement of dense and sparse solves.
pyMOTO has no buckling module, so there is no pyMOTO physics cross-check.

## 🔗 Discretisations with open implementations

| Discretisation | Status | Where | What it adds |
| :-- | :-- | :-- | :-- |
| Higher-order and mixed elements | 🔗 top99neo (with the paper) | Ferrari & Sigmund, *SMO* 2020 | Fixes Q4's bending behaviour; changes which filter is actually needed. |
| Polygonal elements | 🔗 [PolyTop](https://link.springer.com/article/10.1007/s00158-011-0696-x) | Talischi et al., *SMO* 2012 | Unstructured polygonal meshes; suppresses the mesh-bias artefacts of structured quads. |
| Virtual element method | 🔗 with the paper | Antonietti et al., [arXiv:1612.08620](https://arxiv.org/abs/1612.08620); Chi et al., *SMO* 2020 | Arbitrary polygonal and polyhedral elements, including non-convex. |
| Isogeometric (NURBS) | 🔗 IgaTop (with the paper) | Hughes et al., *CMAME* 2005; Gao et al. (IgaTop) | One basis for geometry, analysis and density: no re-meshing, CAD-ready boundaries. |
| Unfitted / embedded (CutFEM, ersatz) | 🔗 [GridapTopOpt.jl](https://github.com/zjwegert/GridapTopOpt.jl) | Burman et al. 2015; Wegert et al., *SMO* 2025 | Crisp boundaries without body-fitted meshing — the natural partner for level-set methods, including the one in [`methods/levelset_rbf.py`](../methods/levelset_rbf.py), which currently uses an ersatz density instead. |

## 📄 Discretisations with no open implementation to start from

| Discretisation | Reference | What it adds |
| :-- | :-- | :-- |
| 📄 Plate and shell elements | Bendsøe & Sigmund 2003, ch. 1 | Thin-walled structures, where a 3-D solid discretisation is wasteful. Related: 3-D thin-walled TO with adaptive meshing, [arXiv:1908.10825](https://arxiv.org/abs/1908.10825). |
| 📄 Beam and frame elements | Michell 1904; Zegard & Paulino, *SMO* 2014 | Needed by the ground-structure parameterisation; a different stiffness assembly entirely. |
| 📄 Meshless / particle methods | Luo et al. 2012 | Avoids meshing, at the cost of awkward essential boundary conditions and expensive shape functions. Mostly of academic interest. |

## References

- E. Andreassen, A. Clausen, M. Schevenels, B. S. Lazarov, O. Sigmund, "Efficient topology optimization in MATLAB using 88 lines of code", *SMO* 43 (2011) 1–16.
- K. Liu, A. Tovar, "An efficient 3D topology optimization code written in Matlab", *SMO* 50 (2014) 1175–1196.
- F. Ferrari, O. Sigmund, "A new generation 99 line Matlab code for compliance topology optimization and its extension to 3D", *SMO* 62 (2020) 2211–2228.
- C. Talischi, G. H. Paulino, A. Pereira, I. F. M. Menezes, "PolyTop", *SMO* 45 (2012) 329–357.
