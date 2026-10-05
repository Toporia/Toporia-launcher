# Models — the physics and the gradients

A model answers "what is optimised": design in, objective, volume, constraints and all
their gradients out. The physics, the filter bookkeeping and the sensitivity analysis live
here — see [`core.composition.Model`](../../core/composition.py). Swapping the model is
how Toporia reaches new physics, new dimensions and new mesh types without touching a
single update rule.

**Status: 2 in Toporia · 24 with open code · 3 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here, registered, tested. |
| 🔗 **Open code** | An open-source engine or code exists. Either wrap it behind a Model, or use it to validate ours. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Model | File | Registry name | Scope |
| :-- | :-- | :-- | :-- |
| ✅ 2-D Q4 plane stress | [`q4.py`](q4.py) | `q4` | Toporia's own engine: 2-D plane stress, structured grid, SIMP, direct sparse solve. Provides compliance, volume and stress; accepts the filter pipeline. |
| ✅ Linear elasticity, pyMOTO | [`pymoto_elastic.py`](pymoto_elastic.py) | `pymoto_elastic` | A pyMOTO module network, which brings its own filters and backpropagates its own gradients. Optional dependency (`pip install pymoto`). |

`q4` is built on [`assembled.py`](assembled.py), the generic model: name a physics engine
and the filters and responses come for free — every response the engine provides features
for, every filter in the pipeline. `pymoto_elastic` is written as a whole model instead,
because pyMOTO brings its own filter and its own gradients.

**So a new engine is not a new model.** Implement
[`core.physics.Physics`](../../core/physics.py) — solve a density to a state, answer a
declared set of `provides` features (`elastic_energy`, `stress`, …) — and every existing
response and filter applies to it unchanged. That is the interface each engine below
should be wrapped behind.

The ceiling today: **2-D, structured grids, linear elastic, direct solves.** Everything in
the first table below is a way past it.

## 🔗 Engines worth wrapping

Ordered roughly by what they add beyond what we already have.

| Engine | Language / licence | Scope | What it would add |
| :-- | :-- | :-- | :-- |
| 🔗 [pyMOTO](https://github.com/aatmdelissen/pyMOTO) | Python · MIT | Module/Signal graph with backpropagated sensitivities; 2-D and 3-D statics and dynamics, thermal, thermo-mechanical, compliant mechanisms, stress, multigrid-preconditioned CG | Already a dependency, but only the elastic part is wrapped. Its thermal, dynamic and 3-D modules are unused. **The cheapest next step in this whole library.** |
| 🔗 [JAX-FEM](https://github.com/deepmodeling/jax-fem) | Python/JAX · Apache-2 | Differentiable GPU FEM; hyperelasticity, plasticity, 3-D unstructured | GPU scale and non-linear materials, with AD instead of hand-derived adjoints. The natural host for anything neural. |
| 🔗 [FEniTop](https://github.com/missionlab/fenitop) | Python/FEniCSx | 2-D and 3-D SIMP over MPI, problems stated in weak form | Unstructured meshes, real geometry, parallel runs, arbitrary PDEs through UFL. Jia, Wang & Zhang, *SMO* 2024. |
| 🔗 [TopOpt_in_PETSc](https://github.com/topopt/TopOpt_in_PETSc) | C++ · open | Fully parallel 3-D minimum compliance on Cartesian grids | The upper bound on resolution — the code behind the giga-voxel wing in Aage et al., *Nature* 2017. [Python wrapper](https://github.com/thsmit/TopOpt_in_PETSc_wrapped_in_Python) and a [transient variant](https://github.com/topopt/TopOpt_in_PETSc_Transient) exist. |
| 🔗 [GridapTopOpt.jl](https://github.com/zjwegert/GridapTopOpt.jl) | Julia · MIT | Level-set TO on unfitted/embedded meshes, AD, PETSc, MPI | The strongest open level-set engine. Cross-language, so best used as a comparison oracle. Wegert et al., *SMO* 2025. |
| 🔗 [TopOpt.jl](https://github.com/JuliaTopOpt/TopOpt.jl) | Julia · MIT | Continuum *and* truss, single and multi-material, binary and continuous, unstructured, all AD | The only mainstream engine treating truss and continuum as one system. |
| 🔗 [MOOSE optimization module](https://mooseframework.inl.gov/modules/optimization/examples/topology_optimization/multimaterial.html) | C++ · LGPL | SIMP and ordered-SIMP multi-material on full MOOSE physics | Coupled multiphysics nothing else here reaches. |
| 🔗 dolfin-adjoint / pyadjoint | Python · LGPL | Automatic adjoints for FEniCS and Firedrake | Adjoints for physics you have not derived by hand. |
| 🔗 [OpenLSTO](https://github.com/M2DOLab/OpenLSTO) | C++ · Apache-2 | Level-set TO with separated FEA and LSM modules | An independent level-set implementation to validate [`methods/levelset_rbf.py`](../methods/levelset_rbf.py) against. |
| 🔗 [beso](https://github.com/calculix/beso) | Python · GPL | BESO driving CalculiX on real CAD meshes; FreeCAD and PrePoMax integration | The cheapest path to "run on an imported STEP part", and an independent BESO reference. |
| 🔗 [PolyTop / PolyMat / PolyStress / PolyDyna](https://link.springer.com/article/10.1007/s00158-011-0696-x) | MATLAB · open | Polygonal finite elements, analysis strictly separated from the optimiser | **The clearest published template for the modularity Toporia is aiming at.** PolyStress is the best open local-stress reference; PolyDyna adds dynamics. |
| 🔗 [Swan](https://github.com/SwanLab/Swan) | MATLAB · open | Density, level set and multiscale in one "topology optimisation laboratory" | Direct prior art for a comparison platform; worth reading for its taxonomy. |
| 🔗 [ToPy](https://github.com/williamhunter/topy) | Python · MIT | 2-D/3-D SIMP on structured grids, config-driven | Little beyond what we have; useful as a 3-D SIMP cross-check. |
| 🔗 [PyTopo3D](https://arxiv.org/abs/2504.05604) | Python · CC-BY-4.0 | 3-D SIMP with STL import of the domain and STL export of the result | **The geometry I/O story** — STL in, STL out — which anything printable will need. |
| 🔗 [topopt (zfergus)](https://github.com/zfergus/topopt) · [topopt (Lagerweij)](https://github.com/AJJLagerweij/topopt) | Python · open | 2-D SIMP, MMA update | Small independent Python ports, handy for cross-checking our OC and MMA. |
| 🔗 [dl4to](https://github.com/dl4to/dl4to) | Python/PyTorch · open | 3-D TO built to interoperate with neural networks; ships the SELTO datasets | The bridge to learned methods, and a ready benchmark harness. |
| 🔗 [PeTTO](https://arxiv.org/abs/2509.06971) | GPU · open | Pseudo-transient, matrix-free TO solvers | An alternative to sparse direct solves on large 3-D grids. |
| 🔗 [STORX](https://arxiv.org/abs/2606.17291) | MATLAB · open | Object-oriented shape *and* topology optimisation | Recent prior art for the abstraction questions in [`../README.md`](../README.md). |
| 🔗 [FormOpt](https://arxiv.org/abs/2601.05709) | Python/FEniCSx · open | Level-set shape optimisation, parallel | Modern level-set reference on unstructured parallel meshes. |
| 🔗 [Fireshape](https://arxiv.org/abs/2005.07264) | Python/Firedrake · open | Shape optimisation by moving mesh, ROL optimisers, automated shape derivatives | The shape-optimisation half of the field, which density methods never touch. |

## 🔗 Engines for other physics

| Engine | Domain | Note |
| :-- | :-- | :-- |
| 🔗 [TOFLUX](https://github.com/UW-ERSL/TOFLUX) | Fluids, multiphysics | Differentiable (JAX) TO for fluidic problems: flow, thermal, transport. Fluid objectives without writing a CFD solver. |
| 🔗 [Meep](https://meep.readthedocs.io/en/latest/Python_Tutorials/Adjoint_Solver/) | Electromagnetics | FDTD with a built-in adjoint solver and density-based TO wrappers. The most widely used engine in photonic inverse design. |
| 🔗 [ceviche](https://github.com/google/ceviche-challenges) | Electromagnetics | Differentiable FDFD/FDTD with autograd; the challenge suite packages standard photonic benchmarks behind one API. |
| 🔗 [SPINS-B](https://github.com/stanfordnqp/spins-b) | Photonics | Gradient-based 2-D/3-D FDFD optimisation with a staged continuation workflow — a well-documented example of continuation done properly. |

Photonics is the second-largest application area of topology optimisation after mechanics.
Tutorial: Christiansen & Sigmund, *JOSA B* 38 (2021).

## 📄 Models with no open implementation to start from

| Model | Reference | Note |
| :-- | :-- | :-- |
| 📄 Finite-strain (geometrically non-linear) elasticity | Buhl, Pedersen & Sigmund, *SMO* 2000; Wang, Lazarov, Sigmund & Jensen, *CMAME* 2014 | A Newton solve inside every iteration, and low-density elements invert unless the void is relaxed. |
| 📄 Transient dynamics with a discrete adjoint | Aage et al. (transient PETSc framework); PolyDyna, *SMO* 2021 | The adjoint must be integrated backwards over the load history. Prerequisite for impact and fatigue work. |
| 📄 Homogenisation / unit-cell model | Sigmund, *IJSS* 1994 (inverse homogenisation) | Computes effective properties of a periodic cell. The entry point to metamaterials and to the multiscale pipeline in [`methods/`](../methods/README.md). |

## References

- A. A. T. M. Delissen, pyMOTO — modular framework for topology optimization with semi-automatic derivatives, [doi:10.5281/zenodo.8138859](https://doi.org/10.5281/zenodo.8138859).
- N. Aage, E. Andreassen, B. S. Lazarov, O. Sigmund, "Giga-voxel computational morphogenesis for structural design", *Nature* 550 (2017) 84–86.
- Y. Jia, C. Wang, X. S. Zhang, "FEniTop: a simple FEniCSx implementation for 2D and 3D topology optimization supporting parallel computing", *SMO* 69 (2024) 140.
- C. Talischi, G. H. Paulino, A. Pereira, I. F. M. Menezes, "PolyTop: a Matlab implementation of a general topology optimization framework using unstructured polygonal finite element meshes", *SMO* 45 (2012) 329–357.
- J. Alexandersen, C. S. Andreasen, "A review of topology optimisation for fluid-based problems", *Fluids* 5 (2020) 29.
