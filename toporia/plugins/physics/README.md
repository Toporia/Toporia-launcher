# Finite elements — discretisation

The element formulation and the assemble-and-solve routine a model uses. Kept separate
from [`models/`](../models/README.md) because the same physics can be discretised many
ways, and the choice of element is itself a thing worth comparing: it decides what the
density field can resolve and where the classic numerical artefacts come from.

**Status: 3 in Toporia · 5 with open code · 3 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Element | File | Scope |
| :-- | :-- | :-- |
| ✅ Q4 plane stress | [`q4_plane_stress.py`](q4_plane_stress.py) | Bilinear quadrilateral, 2 DOF per node, structured grid, column-major numbering, analytic element stiffness. The top88 element. 2-D. |
| ✅ Q4 with buckling | [`q4_buckling.py`](q4_buckling.py) | The Q4 element plus the geometric (stress) stiffness and the generalised eigenproblem for linearised buckling; provides `buckling`. 2-D. |
| ✅ H8 solid | [`h8_solid.py`](h8_solid.py) | Trilinear brick, 3 DOF per node, 2 × 2 × 2 Gauss integration, the element of Liu & Tovar's top3d. 3-D: a scenario with a depth `Lz`. Direct sparse solver, or conjugate gradients with algebraic multigrid (optional `pyamg`) for large meshes. |

Each module is a [`framework.parts.physics.Physics`](../../framework/parts/physics.py) engine:
it solves a density to a state and declares which features it answers (`elastic_energy`,
`stress`) and in which dimensions (`dims`). Adding an element formulation below means
implementing that interface, after which every response and filter in the library that
works in its dimension applies to it unchanged.

**How H8 is checked.** With Poisson's ratio 0, a design that does not vary through the depth
must behave exactly as the 2-D design in plane stress. Its 3-D compliance is then the Q4
compliance divided by the depth, which holds to 1e-12 on the cantilever, the MBB beam and
the drone arm (holes and solid rings included). A test asserts it in
`tests/plugins/test_3d.py`. The finite-difference gradient checks of `toporia check
model:h8` and `toporia check response:stress` cover its compliance and 3-D stress
sensitivities.

### Q4 with buckling

[`q4_buckling.py`](q4_buckling.py) is `Q4PlaneStress` with one more question answered, the
`buckling` feature: the lowest positive **load factors** λ of every load case, from
`(K + λ K_σ) φ = 0`, where `K_σ` is the geometric stiffness of the element stresses of the
linear solution (λ = 3 means the structure buckles at three times the applied load). It
follows Ferrari, Sigmund & Guest, "Topology optimization with linearized buckling criteria
in 250 lines of Matlab", *SMO* 63 (2021) 3045-3066,
[doi:10.1007/s00158-021-02854-x](https://doi.org/10.1007/s00158-021-02854-x), written from
the paper's description. Its choices, so you can judge them:

- `K_σ` of an element uses the solid-material stress at the element centre and is scaled by
  `density^p_sigma` (parameter `p_sigma`, default 4): above the stiffness exponent, so it
  vanishes faster than `K` in void and the artificial buckling modes of the void do not appear.
- Eigenvalues come from SciPy `eigsh` on the pencil `(-K_σ, K)`, largest `μ = 1/λ` first; `K`
  is factorised once and reused in every Lanczos step (shift-invert about zero). Systems under
  600 free degrees of freedom are solved densely.
- The sensitivity of a load factor has the explicit part, the part through `K`, and the part
  through the displacements (`K_σ` depends on `u`), which costs one back-substitution per mode
  with the factorisation of `K` already made.
- **Check.** A cantilever column (4 x 40, 2 elements per unit) gives 0.008231 against Euler's pi^2 E I / (4 L^2) = 0.008225: 0.08 % off. The sensitivity (adjoint term included) matches central finite
  differences to 1e-4 in `tests/plugins/test_buckling.py`.
- pyMOTO has no buckling module, so this model exists only as Toporia's own.
- Under a load in tension there is no buckling; the response then reports a slack constraint.

Two consequences worth knowing before adding anything here:

- **The material law is a part of its own.** The engine declares `uses_interpolation`, so
  SIMP, RAMP or any law in [`interpolations/`](../interpolations/README.md) can be chosen
  in the solver; it no longer has a `penal` of its own.
- **Q4 under-integrates bending and produces checkerboards**, which is the historical
  reason the filters in [`filters/`](../filters/README.md) exist at all. A higher-order or
  mixed element changes that story, so "which element" is a legitimate comparison axis and
  not an implementation detail.

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
