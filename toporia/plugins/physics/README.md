# Finite elements — discretisation

The element formulation and the assemble-and-solve routine a model uses. Kept separate
from [`models/`](../models/README.md) because the same physics can be discretised many
ways, and the choice of element is itself a thing worth comparing: it decides what the
density field can resolve and where the classic numerical artefacts come from.

**Status: 1 in Toporia · 6 with open code · 3 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Element | File | Scope |
| :-- | :-- | :-- |
| ✅ Q4 plane stress | [`q4_plane_stress.py`](q4_plane_stress.py) | Bilinear quadrilateral, 2 DOF per node, structured grid, column-major numbering, analytic element stiffness. The top88 element. |

This module is also Toporia's only [`framework.parts.physics.Physics`](../../framework/parts/physics.py) engine:
it solves a density to a state and declares which features it answers (`elastic_energy`,
`stress`). Adding an element formulation below means implementing that interface, after
which every response and filter in the library applies to it unchanged.

Two consequences worth knowing before adding anything here:

- **The SIMP interpolation is hard-coded** in `solve_fea`, as
  `E = Emin + ρᵖ(E₀ − Emin)`. Making it a choice is what RAMP and multi-material need —
  see [`methods/`](../methods/README.md).
- **Q4 under-integrates bending and produces checkerboards**, which is the historical
  reason the filters in [`filters/`](../filters/README.md) exist at all. A higher-order or
  mixed element changes that story, so "which element" is a legitimate comparison axis and
  not an implementation detail.

## 🔗 Discretisations with open implementations

| Discretisation | Status | Where | What it adds |
| :-- | :-- | :-- | :-- |
| 3-D 8-node hexahedron (H8) | 🔗 top3d (with the paper), [TopOpt_in_PETSc](https://github.com/topopt/TopOpt_in_PETSc), [ToPy](https://github.com/williamhunter/topy) | Liu & Tovar, *SMO* 2014 | The obvious next element. Everything in the library is 2-D today. |
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
