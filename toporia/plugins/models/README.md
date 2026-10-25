# Models — the physics and the gradients

A model answers "what is optimised": design in, objective, volume, constraints and all
their gradients out. The physics, the filter bookkeeping and the sensitivity analysis live
here — see [`framework.parts.model.Model`](../../framework/parts/model.py). Swapping the model is
how Toporia reaches new physics, new dimensions and new mesh types without touching a
single update rule.

**Status: 11 in Toporia · 24 with open code · 3 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here, registered, tested. |
| 🔗 **Open code** | An open-source engine or code exists. Either wrap it behind a Model, or use it to validate ours. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Model | File | Registry name | Scope |
| :-- | :-- | :-- | :-- |
| ✅ 2-D Q4 plane stress | [`q4.py`](q4.py) | `q4` | Toporia's own engine: 2-D plane stress, structured grid, SIMP, direct sparse solve. Provides compliance, volume and stress; accepts the filter pipeline. |
| ✅ 2-D Q4 with buckling | [`q4_buckling.py`](q4_buckling.py) | `q4_buckling` | Adds the `buckling_load` objective/constraint, retaining compliance, volume, stress, filters and material laws. |
| ✅ 2-D Q4 compliant mechanism | [`q4_mechanism.py`](q4_mechanism.py) | `q4_mechanism` | Linear Q4 with density-independent point springs, opaque point-displacement probes and signed output sensitivities. Shared sparse LU for all real and virtual loads. |
| ✅ 2-D Q4 with vibration | [`q4_dynamic.py`](q4_dynamic.py) | `q4_dynamic` | Static elasticity, natural frequencies and harmonic response. |
| ✅ Vibration, pyMOTO | [`pymoto_dynamic.py`](pymoto_dynamic.py) | `pymoto_dynamic` | Independent pyMOTO eigenproblem and sensitivities; optional dependency. |
| ✅ 2-D Q4, large deformation | [`q4_nonlinear.py`](q4_nonlinear.py) | `q4_nonlinear` | Geometrically non-linear elasticity (large displacements, small strains) on Q4: total Lagrangian, Green–Lagrange strain, St Venant–Kirchhoff material, Newton–Raphson with load steps. Provides end compliance and volume; accepts the filter pipeline. See below. |
| ✅ 3-D H8 bricks | [`h8.py`](h8.py) | `h8` | Toporia's own 3-D engine (a scenario with a depth): H8 bricks, any material law, direct or multigrid solver. Provides compliance, volume and 3-D stress; accepts the filter pipeline. Switching the GUI's Design section to 3-D selects it. |
| ✅ Linear elasticity, pyMOTO | [`pymoto_elastic.py`](pymoto_elastic.py) | `pymoto_elastic` | A pyMOTO module network, which brings its own filters and backpropagates its own gradients. Optional dependency (`pip install pymoto`). |
| ✅ 2-D Q4 heat conduction | [`q4_heat.py`](q4_heat.py) | `q4_heat` | Steady heat conduction on Toporia's Q4 grid: uniform heat generation, supports as heat sinks, conductivity from the material law. Provides thermal compliance and volume; accepts the filter pipeline. |
| ✅ 3-D H8 heat conduction | [`h8_heat.py`](h8_heat.py) | `h8_heat` | The same on eight-node bricks (a scenario with a depth). |
| ✅ Heat conduction, pyMOTO | [`pymoto_heat.py`](pymoto_heat.py) | `pymoto_heat` | pyMOTO's `AssemblePoisson` network: the cross-check of `q4_heat`, giving the same thermal compliance to 1e-9. Optional dependency (`pip install pymoto`). |

### Compliant mechanisms (`q4_mechanism`)

The separate [physics engine](../physics/q4_mechanism.py) adds ground springs
to the stiffness matrix and uses that same matrix for every adjoint. It accepts
`Scenario.point_springs`, each a `PointSpring(x, y, stiffness, dof="x")`; `dof`
can also be `y`. Coordinates are in mm and snap to the nearest node. Coincident
spring stiffnesses add. Positive springs count as supports, so a spring-only
scenario does not acquire an unrequested default clamp. Rigid-body restraint is
checked before solving. Other models reject spring scenarios; they never
silently omit these stiffnesses.

Compliance is external work `f^T*u`, including spring energy; its density
derivative differentiates the material stiffness only. The new
`output_displacement` response maximises signed motion at an output point with
one virtual-load solve. Use MMA for its mixed-sign gradients. The existing
`q4` source and results are unchanged. See [Force Inverter](../problems/README.md#force-inverter)
for a runnable example. An optional independent pyMOTO assembly and backpropagated
gradient agree in `tests/plugins/test_mechanism_pymoto.py`; this is a cross-check,
not another selectable pyMOTO model.

### Buckling (`q4_buckling`)

The model exposes the linearised buckling formulation of
[Ferrari, Sigmund & Guest (2021)](https://doi.org/10.1007/s00158-021-02854-x).
In the GUI, pick *2-D Q4 with buckling (Toporia)* or the *Column Buckling* preset.
Its buckling objective works with MMA; a buckling constraint requires a multi-constraint
updater such as `pymoto_mma`, `mmapy_mma` or `nlopt_mma`. The preset uses `pymoto_mma`:
`toporia run "Column Buckling" --set m=0.3 --set max_iter=120`.
The static Q4 engine is unchanged. See the [physics details](../physics/README.md).

### Heat conduction (the heat-sink problem)

`q4_heat`, `h8_heat` and `pymoto_heat` minimise the **thermal compliance** of a plate that
generates heat and is cooled through heat sinks: Bendsøe & Sigmund, *Topology Optimization*
(2003), section 1.5; Gersborg-Hansen, Bendsøe & Sigmund, *SMO* 31 (2006) 251-259,
[doi](https://doi.org/10.1007/s00158-005-0584-3). In the GUI choose the model under *Physics*; the objective list then offers
*Thermal compliance* (objectives follow from what the physics provides), and the *Heat Sink*
preset sets it all up. On the command line: `toporia run "Heat Sink"` (a 50 × 50 mesh,
`q4_heat+oc`, 100 iterations in about two seconds), or `toporia run "Heat Sink" --set
m=1` for a finer one. How a scenario maps onto heat conduction is in
[`../physics/README.md`](../physics/README.md).
| ✅ 2-D Q4 with vibration | [`q4_dynamic.py`](q4_dynamic.py) | `q4_dynamic` | The Q4 engine plus a mass matrix ([`physics/q4_dynamic.py`](../physics/q4_dynamic.py)). Everything `q4` offers, and in addition the objectives *fundamental frequency* (maximise; also a constraint, *at least*) and *dynamic compliance* of a harmonic load. Pair it with MMA. |
| ✅ Vibration, pyMOTO | [`pymoto_dynamic.py`](pymoto_dynamic.py) | `pymoto_dynamic` | The same eigenfrequency problem on pyMOTO's `AssembleMass` and `EigenSolve`: an independent check of `q4_dynamic` (equal eigenvalues to 1e-13 on the same density). Objective: fundamental frequency. Optional dependency. |

`q4` is built on [`assembled.py`](assembled.py), the generic model: name a physics engine
and the filters and responses come for free — every response the engine provides features
for, every filter in the pipeline. `pymoto_elastic` is written as a whole model instead,
because pyMOTO brings its own filter and its own gradients.

**So a new engine is not a new model.** Implement
[`framework.parts.physics.Physics`](../../framework/parts/physics.py) — solve a density to a state, answer a
declared set of `provides` features (`elastic_energy`, `stress`, …) — and every existing
response and filter applies to it unchanged. That is the interface each engine below
should be wrapped behind.

**Vibration in the GUI and on the command line.** In the GUI choose the model *2-D Q4 with
vibration (Toporia)* (or load the preset *Vibrating Beam*); the objective list then offers
*Fundamental frequency (maximise)* and *Dynamic compliance (harmonic load)*, and the model
parameters (mass density, the low-density fix, mass type, attached mass) appear with the
others. On the command line `toporia run "Vibrating Beam"` runs the preset; for your own
scenario set `method` to `q4_dynamic+mma` and the objective to `{"type": "eigenfrequency"}`,
e.g. `toporia run "Vibrating Beam" --set method.attached_mass=4`. Eigenvalue
sensitivities change sign, so use MMA, not OC. See [`physics/`](../physics/README.md#vibration-eigenfrequencies-and-harmonic-response).

The ceiling today: **2-D, structured grids, linear elastic, direct solves.** Everything in
the first table below is a way past it.

## 🔗 Engines worth wrapping

Ordered roughly by what they add beyond what we already have.

| Engine | Language / licence | Scope | What it would add |
| :-- | :-- | :-- | :-- |
| 🔗 [pyMOTO](https://github.com/aatmdelissen/pyMOTO) | Python · MIT | Module/Signal graph with backpropagated sensitivities; 2-D and 3-D statics and dynamics, thermal, thermo-mechanical, compliant mechanisms, stress, multigrid-preconditioned CG | Elastic, thermal and dynamic models are wrapped. Spring-loaded output displacement is independently cross-checked in tests; selectable mechanism, thermo-mechanical and 3-D network models remain possible additions. |
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
