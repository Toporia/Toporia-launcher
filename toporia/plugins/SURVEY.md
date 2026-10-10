# Public open-source topology-optimisation codes: survey for Toporia

Date of survey: 2026-10-11. Read-only on the repo.

## Method and caveats

- Catalogue baseline: `toporia/plugins/TODO.md` does NOT exist. The slot READMEs (`toporia/plugins/*/README.md`) are absent from the checked-out branch `integration/wave-1` and were read from `.claude/worktrees/agent-a78ad3446c3c4f176/toporia/plugins/*/README.md`. Rows marked "NEW" are not in those READMEs.
- Check column ("Chk"):
  - **V** = URL fetched or queried by GitHub/PyPI API this session, so the link resolved and the licence is as stated.
  - **S** = seen in search results from a reputable host, not fetched (resolves very likely, licence not independently checked).
  - **U** = UNVERIFIED (could not fetch or confirm).
- "Licence" is what GitHub's licence metadata, PyPI metadata or the page itself says. "none stated" means the repo/page declares nothing (not a grant of rights). DTU educational codes carry only an "authors reserve all rights ... intended for educational purposes" disclaimer: they are fine to run (BRIDGE/ORACLE) but porting verbatim needs care.
- Entry route: IMPORT = pip-installable Python package; BRIDGE = MATLAB script runnable unchanged; MAKE = port from code/paper; ORACLE = other language, compare only.
- GitHub unauthenticated API quota was exhausted partway, so some repos are S rather than V.
- Python 3.14 note: where PyPI `requires_python` excludes 3.14 this is stated.

---

## 1. Whole-method / framework packages (Python)

| # | Name | URL | Lang | Licence | Implements | Slot | Route | Chk |
|---|------|-----|------|---------|-----------|------|-------|-----|
| 1 | pyMOTO 2.0.1 | https://github.com/aatmdelissen/pyMOTO | Python | MIT | Module/signal graph, backprop sensitivities; statics, dynamics, thermal, compliant mechanisms, stress; MG-CG | physics/model + whole method | IMPORT (`pip install pymoto`, py>=3.9, pure wheel) | V |
| 2 | **topoptlab 1.0.0 (NEW)** | https://github.com/stefanhiemer/topoptlab | Python | GPL-3.0 | Modified SIMP/RAMP/Hashin-Shtrikman interpolations; sens./density filters, Langelaar AM filter, Guest/Sigmund/**volume-conserving** projections; MMA/GCMMA, OC, gradient descent, Barzilai-Borwein; elasticity, heat conduction, thermal expansion, Cahn-Hilliard; CHOLMOD, AMG, geometric MG. JOSS 2026 | interpolation, filter, updater, physics, whole method | IMPORT (`pip install topoptlab`, **py>=3.12.4**, pure wheel). GPL-3 is copyleft, so safer as ORACLE or optional plug-in | V |
| 3 | **pytopo3d 0.3.0 (NEW)** | https://github.com/jihoonkim888/PyTopo3D | Python | MIT | 3-D SIMP + OC, STL import of domains/obstacles, STL export (arXiv 2504.05604) | whole method, problem, post-processor (STL) | IMPORT (`pip install pytopo3d`, py>=3.10) | V |
| 4 | **scikit-topt 0.3.10 (NEW)** | https://github.com/kevin-tofu/scikit-topt | Python | Apache-2.0 | Algorithm-development library on scikit-fem/scipy, parameter-transition visualisation (JOSS 2025) | whole method, updater | IMPORT (`pip install scikit-topt`, import `sktopt`). **PyPI requires py<3.14**, so it will not install on 3.14 | V |
| 5 | topopt (zfergus) 0.0.1a1 | https://github.com/zfergus/topopt | Python | MIT | Min-compliance, MMA, 2-D (docs topopt.readthedocs.io) | whole method | IMPORT (alpha sdist on PyPI, 2020) or MAKE; stale since 2022 | V |
| 6 | SolidsOpt 0.1 (NEW) | https://pypi.org/project/SolidsOpt | Python | MIT | 2-D BESO, ESO, SIMP | updater (ESO/BESO), whole method | IMPORT (sdist; tiny, low quality likely) | V (PyPI) |
| 7 | ToPy | https://github.com/williamhunter/topy | Python | NOASSERTION (README says MIT + CC-BY-SA per PyPI string of an UNRELATED pkg) | Compliance, mechanism, heat conduction, 2-D/3-D, Pysparse | whole method | MAKE/ORACLE. **PyPI `topy` is an unrelated "typo fixer" package, not installable**; last push 2022 | V |
| 8 | DTU Python TopOpt (topopt.py, topopt_cholmod.py) | https://www.topopt.mek.dtu.dk/apps-and-software/Topology-optimization-codes-written-in-Python | Python | none stated (educational) | 88-line-style code, CVXOPT CHOLMOD variant; maintained by N. Aage; origin of topoptlab | whole method | MAKE/ORACLE | V |
| 9 | AJJLagerweij/topopt | https://github.com/AJJLagerweij/topopt | Python | MIT | Small TO educational code | whole method | MAKE/ORACLE | V |
| 10 | topo-fenics (55-line) | https://github.com/iitrabhi/topo-fenics | Python/FEniCS | MIT | SIMP, parallel, multi-load, 2-D/3-D (Bhagat et al., arXiv 2012.08208) | whole method | ORACLE (needs FEniCS, awkward on Windows) | V |
| 11 | FEniTop | https://github.com/missionlab/fenitop | Python/FEniCSx | GPL-3.0 | 2-D/3-D SIMP, MPI, UFL weak forms, AD | whole method, physics | ORACLE | V |
| 12 | PyTOPress (NEW) | https://github.com/PrabhatIn/PyTOPress (link given in arXiv 2410.22131) | Python | unknown | Design-dependent pressure loads, MMA, NumPy/SciPy | problem/physics (pressure load) | MAKE. **Repo URL returned 404 on 2026-10-11 (API and fetch): UNVERIFIED availability** | U |
| 13 | PyHexTop (NEW) | https://github.com/PrabhatIn/PyHexTop | Python | none stated | Hexagonal-element 2-D TO, port of HoneyTop90 (arXiv 2310.01968) | representation (hex grid) | MAKE | V |
| 14 | pygpto (NEW) | https://github.com/jnorato/pygpto | Python | none stated | Geometry projection method (bars/plates), port of GPTO | representation (geometry projection) | MAKE | V |
| 15 | TopOpt_in_PETSc wrapped in Python | https://github.com/thsmit/TopOpt_in_PETSc_wrapped_in_Python | Python/C++ | LGPL-2.1 | Python layer over PETSc TO, extended functionality (Smit et al., SMO 2021 educational) | whole method | ORACLE (needs PETSc, Linux) | V |
| 16 | torch-fem 0.13.1 (NEW) | https://github.com/meyer-nils/torch-fem | Python/PyTorch | MIT (copyright line in PyPI licence field) | GPU differentiable FEM; MBB and 3-D TO examples, autograd vs analytic sensitivities | physics/model + whole method | IMPORT (`pip install torch-fem`, py>=3.10, needs torch) | V (PyPI) |
| 17 | JaxSSO 1.0.1 (NEW) | https://github.com/GaoyuanWu/JaxSSO | Python/JAX | MIT | Differentiable FEA for beams/MITC4 shells; shape/size/topology | physics/model | IMPORT (`pip install JaxSSO`) | V |
| 18 | JAX-FEM 0.0.12 | https://github.com/deepmodeling/jax-fem | Python/JAX | **GPL-3.0** (GitHub); PyPI classifier says BSD, licence text is GPL | Differentiable GPU FEM, hyperelasticity, plasticity, 3-D, TO examples | physics/model | IMPORT (`pip install jax-fem`, py>=3.12, pure wheel; JAX on Windows is CPU-only unless WSL) | V |
| 19 | SOPTX (on FEALPy) (NEW) | https://github.com/weihuayi/soptx | Python | NOASSERTION; FEALPy 3.4.0 on PyPI says "GNU" | Multi-backend (NumPy/PyTorch/JAX) TO decoupled from analysis (arXiv 2505.02438) | whole method | ORACLE/MAKE; SOPTX itself not on PyPI | V (GitHub) |
| 20 | AuTO | https://github.com/UW-ERSL/AuTO | Python/JAX notebooks | GPL-3.0 | AD for compliance, compliant mechanism, microstructure design | response (AD sensitivities) | MAKE/ORACLE; not pip, Colab notebooks | V |
| 21 | TOFLUX | https://github.com/UW-ERSL/TOFLUX | Python/JAX | **none stated** | Differentiable multiphysics fluid/structure/thermal TO, MMA, NN parameterisation | physics/model | MAKE only until a licence is added; JAX, Optax, Flax deps | V |
| 22 | neural-structural-optimization (google-research) | https://github.com/google-research/neural-structural-optimization | Python/TF+autograd | Apache-2.0 | Neural reparameterisation (CNN) of density; NLopt MMA; benchmark suite | representation (neural), problem/benchmark set | MAKE; **not pip-installable**, needs TensorFlow | V |
| 23 | dl4to | https://github.com/dl4to/dl4to | Python/PyTorch | Apache-2.0 | 3-D TO with FD elasticity solver, SIMP, UNets, neural reparam., supervised/unsupervised learning | representation (neural), whole method | IMPORT only via `pip install git+https://github.com/dl4to/dl4to` (**not on PyPI**; PyPI `deeptl` is unrelated); pins pyvista 0.38.1 | V |
| 24 | TOuNN | https://github.com/UW-ERSL/TOuNN | Python/PyTorch | GPL-3.0 | Density as an NN (Chandrasekhar & Suresh) | representation (neural) | MAKE/ORACLE. Catalogue link `ersl.wisc.edu/software/TOuNN.zip` not re-checked: U | V (GitHub) |
| 25 | nn4topopt | https://github.com/ISosnovik/nn4topopt | Python | none stated | CNN prediction of TO result (Sosnovik & Oseledets) | whole method (surrogate) | ORACLE | V |
| 26 | SOLO | https://github.com/deng-cy/deep_learning_topology_opt | MATLAB | MIT | Self-directed online learning surrogate (Nat. Commun. 2022) | whole method | BRIDGE (MATLAB) | V |
| 27 | TopoDiff / TopologyGAN | https://decode.mit.edu/projects/topodiff/ ; NVIDIA PhysicsNeMo docs "TopoDiff (external contribution from MIT)" | Python | not checked | Conditional diffusion / cGAN generation of topologies; TopologyGAN code is TensorFlow | whole method (generative) | ORACLE. GitHub repos and licences UNVERIFIED | U |
| 28 | fenics_topopt_foam (NEW) | https://github.com/diego-hayashi/fenics_topopt_foam | Python | GPL-3.0 | OpenFOAM + FEniCS/dolfin-adjoint flow TO | physics (fluid) | ORACLE | V |
| 29 | cashocs 2.11.0 (NEW) | https://pypi.org/project/cashocs | Python | GPL-3 | Adjoint shape optimisation and optimal control; level-set TO demos; needs FEniCS | physics/updater | ORACLE (FEniCS dependency) | V (PyPI) |
| 30 | Lestofire (NEW) | https://software.llnl.gov/news/2020/11/30/lestofire-new/ | Python/Firedrake | UNVERIFIED | Level-set TO with pyadjoint + Feppon null-space optimiser (arXiv 2005.07264) | representation (level set) | ORACLE; Firedrake not supported on native Windows | S |
| 31 | calculix/beso | https://github.com/calculix/beso | Python | LGPL-3.0 | BESO/ESO driving CalculiX; stress/frequency/buckling criteria | updater (hard-kill BESO) | ORACLE (needs CalculiX) | V |
| 32 | Zuo & Xie 100-line BESO Python (NEW) | https://www.rmit.edu.au/research/centres-collaborations/centre-for-innovative-structures-and-materials/software | Python/Abaqus | none stated | 3-D BESO scripts (BESO_Basic.py, Adv_ML, Adv_NL with large deformation) | updater (BESO), nonlinear | ORACLE (requires Abaqus) | S |

## 2. MATLAB educational and paper-supplement codes

### 2a. Core compliance codes (Sigmund / DTU lineage)

| # | Name | URL | Licence | Implements | Slot | Route | Chk |
|---|------|-----|---------|-----------|------|-------|-----|
| 33 | top.m, 99-line (Sigmund, SMO 2001) | https://www.topopt.mek.dtu.dk/apps-and-software/a-99-line-topology-optimization-code-written-in-matlab | none stated | OC, mesh-independence filter, 2-D compliance; page names multiple loads, other filters, passive areas as student extensions only | whole method | BRIDGE | V |
| 34 | top88.m, top82.m, top71.m, top110.m (Andreassen et al., SMO 2011) | https://www.topopt.mek.dtu.dk/apps-and-software/efficient-topology-optimization-in-matlab | none stated | top88 sens./density filter; **top82 = PDE (Helmholtz) filter**; top71 = conv2 filter; top110 = Heaviside filter | filter (PDE, Heaviside), whole method | BRIDGE / ORACLE | V |
| 35 | top99neo.m, top3D125.m (Ferrari & Sigmund, SMO 2020) | https://www.topopt.mek.dtu.dk/apps-and-software/new-99-line-topology-optimization-code-written-in-matlab | "authors reserve all rights" disclaimer; needs `fsparse` (Fast package) | **Volume-preserving Heaviside projection (Newton-found eta, ft=3)**, passive domain, filter BCs, p/beta continuation, fast OC; 3-D code | filter, schedule, whole method | BRIDGE (fsparse dependency) | V |
| 36 | TopBuck250 (Ferrari, Sigmund & Guest, SMO 2021) | https://www.topopt.mek.dtu.dk/apps-and-software/topbuck250 ; paper arXiv 2101.02973 | none stated | Linearised buckling load factor as objective/constraint, KS aggregation, MMA-like OC | response (buckling), physics | BRIDGE | V |
| 37 | tops140 (Uihlein, Sigmund, Stingl) (NEW) | https://www.topopt.mek.dtu.dk/apps-and-software/stochastic-gradient-matlab ; arXiv 2505.10421 | none stated | Stochastic gradient descent for uncertain loads/damage, clamp and dynamic MBB | updater (stochastic), problem | BRIDGE | V |
| 38 | TopTMC (Frederiksen, Sigmund, Ferrari) (NEW) | https://www.topopt.mek.dtu.dk/apps-and-software/Top_ThirdMediumContact ; arXiv 2512.00133 | none stated | Third-medium contact, hyperelastic, self-contact TO, 2-D, Newton incremental solver | physics (nonlinear/contact) | BRIDGE / MAKE | V |
| 39 | top200EM (Christiansen & Sigmund) (NEW) | https://www.topopt.mek.dtu.dk/apps-and-software/Matlab-codes-electromagnetic-topology-optimization | none stated | 200-line photonics inverse design (metalens); plus 5 COMSOL models | physics (EM), problem | BRIDGE (separate physics) | V |
| 40 | topcut (Sigmund group, SMO 2020) | https://www.topopt.mek.dtu.dk/apps-and-software/top-cut-code-paper | none stated | Level set via density methods with cut elements and length-scale control | representation (level set), filter | BRIDGE | V |
| 41 | Scalable 3-D matrix-free MG MATLAB = TOP3D_XL | https://github.com/PSLer/TOP3D_XL ; DTU page https://www.topopt.mek.dtu.dk/apps-and-software/scalable-3d-matrix-free-matlab-code | BSD-2-Clause | Matrix-free geometric MG, up to 128 M hex elements, porous infill, arbitrary voxel domains | physics solver, representation | BRIDGE / ORACLE | V |
| 42 | deHomTop808 (Woldseth, Sigmund, Jensen) (NEW) | arXiv 2405.14321 ; SMO doi 10.1007/s00158-024-03880-1 | UNVERIFIED (code in paper/DTU) | Rank-2 multiscale TO + phasor dehomogenisation, 808 lines | representation (multiscale) | MAKE / BRIDGE | S |
| 43 | DTU large-scale and misc. apps | https://www.topopt.mek.dtu.dk/apps-and-software | various | Also: TopOpt_in_PETSc (C++), stream-surface de-homogenisation (C++), TopOptShape app | various | ORACLE | V |

### 2b. Other educational density / compliance codes

| # | Name | URL | Licence | Implements | Slot | Route | Chk |
|---|------|-----|---------|-----------|------|-------|-----|
| 44 | top3d 169-line (Liu & Tovar, SMO 2014) | https://link.springer.com/article/10.1007/s00158-014-1107-x ; code http://top3dapp.com (redirects to http://www.top3d.app/) | none stated | 3-D, **instructions for multiple loads, compliant mechanism, heat conduction**, SQP/MMA hooks | physics, whole method | BRIDGE | S (paper), U (redirect target not fetched) |
| 45 | TOPress (100 lines, Kumar, SMO 2023) (NEW) | https://github.com/PrabhatIn/TOPress ; arXiv 2303.14690 | none stated | Darcy-law pressure loads, MMA | problem/physics (load model) | BRIDGE | V |
| 46 | TOPress3D, HoneyTop90, SoRoTop (NEW) | https://github.com/PrabhatIn/TOPress3D ; .../HoneyTop90 ; .../SoRoTop | none stated | 3-D pressure loads; hexagonal elements 90-line; soft pneumatic robots | physics, representation | BRIDGE | V |
| 47 | PolyTop / PolyMat / PolyStress (Paulino group) | https://paulino.scholar.princeton.edu/software/topology-optimization (fetch 403, found via search) ; PolyStress doi 10.1007/s00158-020-02760-8 | none stated (Springer supplementary) | Polygonal meshes; multi-material many-volume constraints; **augmented-Lagrangian local stress** | representation (polygons), response (stress), updater (AL) | BRIDGE / MAKE | S |
| 48 | GRAND, GRAND3 (Zegard & Paulino, SMO 2014/2015) | https://paulino.princeton.edu/journal_papers/2014/SMO_14_GRAND.pdf | none stated (supplementary) | Ground-structure truss layout, 2-D and 3-D, arbitrary domains | representation (truss) | BRIDGE / MAKE | S |
| 49 | Challis 129-line discrete level set (SMO 2010) | https://link.springer.com/article/10.1007/s00158-009-0430-0 (not fetched) | none stated | Discrete level-set TO | representation (level set) | MAKE | U (URL) |
| 50 | Otomori et al. reaction-diffusion level set (SMO 2015) | http://www.osdel.me.kyoto-u.ac.jp/members/yamada/codes.html (as quoted by paper); paper PDF https://repository.kulib.kyoto-u.ac.jp/dspace/bitstream/2433/201405/1/s00158-014-1190-z.pdf | none stated | Level set evolved by reaction-diffusion; hole nucleation | representation (level set), updater | BRIDGE | U (download page not fetched) |
| 51 | **88-line RBF parameterised level set (Wei, Li, Li & Wang, SMO 2018) (NEW)** | https://research.monash.edu/en/publications/an-88-line-matlab-code-for-the-parameterized-level-set-method-bas/ | none stated (appendix) | RBF-parameterised level set, compliance | representation (level set) | MAKE / BRIDGE | S |
| 52 | TOPRBF_SiPESC (NEW) | https://github.com/appreciator/TOPRBF_SiPESC | MIT | Python port of RBF level set for SiPESC CAE | representation (level set) | ORACLE | V |
| 53 | GFLS262 (PolyU, SMO 2024) (NEW) | doi 10.1007/s00158-024-03891-y | UNVERIFIED | Level set via estimated gradient field on body-fitted mesh | representation (level set) | MAKE | S |
| 54 | MMC188 (Zhang et al., SMO 2016) and 3-D MMC256 (Du et al., SMO 2022) (NEW) | arXiv 2201.02491 (3-D) ; MMC188 in SMO 2016 appendix | none stated | Moving morphable components 2-D / 3-D | representation (components) | MAKE | S |
| 55 | GPTO (Smith & Norato, SMO 2020) | https://github.com/jnorato/GPTO | none stated | Geometry projection, bars, IPOPT/MMA | representation (geometry projection) | BRIDGE | V |
| 56 | Han, Xu, Liu 137-line geometrically nonlinear BESO (SMO 2021) (NEW) | https://pure.nwpu.edu.cn/en/publications/an-efficient-137-line-matlab-code-for-geometrically-nonlinear-top/ | none stated (appendix) | Large-displacement BESO, total Lagrangian + Newton-Raphson, "educational use only" | physics (nonlinear), updater (BESO) | MAKE | S |
| 57 | Chen, Zhang, Zhu 213-line geometrically nonlinear code (SMO 2019) (NEW) | https://link.springer.com/doi/10.1007/s00158-018-2138-5 | none stated | **Uses ANSYS APDL for FEA** (additive hyperelasticity) | physics (nonlinear) | MAKE (not BRIDGE: ANSYS required) | S |
| 58 | Deng, Vulimiri, To 146-line 3-D stress **sensitivity** code (2021) (NEW) | https://arxiv.org/pdf/2104.01210 | none stated, "educational purposes only" | 3-D p-norm stress sensitivity (adjoint) with MMA driver, FD check | response (stress) | MAKE | V (arXiv) |
| 59 | Xia & Breitkopf energy-based homogenisation code (SMO 2015) | doi 10.1007/s00158-015-1294-0 | none stated | Material design, extreme moduli, periodic BCs, on top88 | problem/response (homogenisation) | MAKE | S |
| 60 | Zheng, Yi, Peng, Yoon multi-material 2-D/3-D (Appl. Sci. 2024) (NEW) | https://doaj.org/article/077f168c775e4d16a78387b67799ae8b | open access (paper) | Multi-material, mapping-based interpolation, on 88-line base | interpolation (multi-material) | MAKE | S |
| 61 | iga_top120 / iga_top3D257 (arXiv 2504.08233) and IgaTop 56-line | https://arxiv.org/pdf/2504.08233 | UNVERIFIED | Isogeometric TO, Bezier extraction | representation (IGA) | MAKE | S |
| 62 | ABM 168-line adaptive bubble method (SMO 2023) (NEW) | https://pure.nwpu.edu.cn/en/publications/a-168-line-matlab-code-for-topology-optimization-with-the-adaptiv | none stated | Bubble insertion for hole nucleation | updater / representation | MAKE | S |
| 63 | TOSSE 51-line (Torre et al.) | https://github.com/vlatorre847/TOSSE | GPL-3.0 | Shortest-possible 2-D TO | whole method | MAKE | V |
| 64 | TOP2DFVT (F1000Research 2024) (NEW) | https://pmc.ncbi.nlm.nih.gov/articles/PMC11512726 | CC-BY paper; code UNVERIFIED | Finite-volume theory instead of FE; SIMP and RAMP | physics (discretisation) | MAKE | S |
| 65 | Proportional TO (Biyikli & To, PLoS ONE 2015) | http://www.ptomethod.org | none stated | Non-gradient redistribution; stress and compliance MATLAB programs | updater (baseline) | MAKE | U (site not fetched) |
| 66 | MFSE MATLAB code (Front. Mech. Eng. China 2021) (NEW) | https://journal.hep.com.cn/fme/EN/1159590435079381735 | UNVERIFIED | Material-field series expansion TO | representation (series expansion) | MAKE | S |
| 67 | Educational fluid TO in MATLAB (arXiv 2207.13695) (NEW) | https://arxiv.org/pdf/2207.13695 | UNVERIFIED | Density-based Navier-Stokes TO tutorial and code | physics (fluid) | MAKE | S |
| 68 | STORX (Mirzendehdel & Suresh) (NEW) | https://github.com/DEL-KU/storx ; arXiv 2606.17291 | MIT | OO shape + topology framework: SIMP/RAMP, level set, thermal/thermoelastic/fluid; needs Optimization, PDE, Image Processing toolboxes | whole method | BRIDGE | V |
| 69 | Swan | https://github.com/SwanLab/Swan | none stated | Density and level-set TO lab, 2-D/3-D, mechanisms | whole method | BRIDGE / ORACLE | V |
| 70 | MultiscaleTopOpt (LLNL) | https://github.com/LLNL/MultiscaleTopOpt | MIT | 3-D multiscale TO with lattice surrogates | representation (multiscale) | BRIDGE | V |
| 71 | GGP-Matlab, GPTO-related, SSM | https://github.com/topggp/GGP-Matlab ; https://github.com/PengWeiScut/SSM | none stated | Geometry-based explicit TO; stiffness spreading | representation | BRIDGE | V |
| 72 | topASA (Rostami) | https://github.com/Hossein-Rostami/Topology-Optimization-with-adaptive-Simulated-Annealing | none stated | Metaheuristic baseline | updater (baseline) | BRIDGE | V |

## 3. Julia / C++ frameworks (ORACLE only)

| # | Name | URL | Lang | Licence | Implements | Slot | Route | Chk |
|---|------|-----|------|---------|-----------|------|-------|-----|
| 73 | TopOpt.jl | https://github.com/JuliaTopOpt/TopOpt.jl | Julia | **MIT** (LICENSE.md fetched; GitHub API says NOASSERTION) | Truss + continuum, binary + continuous, multi-material, stress, buckling, AD, heat | whole method | ORACLE | V |
| 74 | GridapTopOpt.jl | https://github.com/zjwegert/GridapTopOpt.jl | Julia | MIT | Parallel level-set TO (arXiv 2405.10478) | representation (level set) | ORACLE | V |
| 75 | topopt_jl (Pollini) (NEW) | https://github.com/pollinico/topopt_jl | Julia | GPL-3.0 | Julia port of top88 | whole method | ORACLE | V |
| 76 | OpenLSTO | https://github.com/M2DOLab/OpenLSTO | C++ | Apache-2.0 | Level-set TO, SLP updater | representation (level set), updater (SLP) | ORACLE | V |
| 77 | TopOpt_in_PETSc and _Transient | https://github.com/topopt/TopOpt_in_PETSc ; .../TopOpt_in_PETSc_Transient | C++ | GitHub: none (main), LGPL-2.1 (Transient) | 3-D parallel compliance; transient dynamics | physics | ORACLE | V |
| 78 | ParOpt | https://github.com/smdogroup/paropt | C++/Cython | LGPL-3.0 per docs (GitHub shows NOASSERTION) | Interior-point and trust-region optimiser for large problems | updater | **Not on PyPI**; build from source with MPI | V |
| 79 | FreeFEM level-set/shape tutorials (Allaire, Dapogny) (NEW) | https://membres-ljk.imag.fr/Charles.Dapogny/tutosto.html | FreeFEM | UNVERIFIED | Educational FreeFEM codes, mmg remeshing | representation (level set, mesh evolution) | ORACLE (`pyfreefem` on PyPI is GPL-3 glue) | S |
| 80 | Laurain FEniCS level-set code (SMO 2018) (NEW) | arXiv 1705.01442 | Python/FEniCS | UNVERIFIED | Educational level-set compliance code | representation (level set) | ORACLE | S |
| 81 | Kratos TopologyOptimizationApplication (NEW) | search result only; Kratos Multiphysics | C++/Python | UNVERIFIED | SIMP compliance | whole method | ORACLE | U |

## 4. Optimisers, solvers, benchmarks

| # | Name | URL | Lang | Licence | Implements | Slot | Route | Chk |
|---|------|-----|------|---------|-----------|------|-------|-----|
| 82 | mmapy 0.3.1 (Deetman GCMMA-MMA-Python) | https://github.com/arjendeetman/GCMMA-MMA-Python ; `pip install mmapy` | Python | **GPL-3.0** (from Svanberg's GPL MATLAB) | MMA and GCMMA | updater | IMPORT (pure wheel, py>=3.6). GPL-3 copyleft | V |
| 83 | nullspace-optimizer 1.3.0 (Feppon) | https://gitlab.com/florian.feppon/null-space-optimizer ; `pip install nullspace_optimizer` | Python | **GPL-3** | Null-space constrained optimiser for level-set and density TO | updater | IMPORT (pure wheel, py>=3.9). GPL-3 | V (PyPI + docs) |
| 84 | NLopt 2.11.0 | https://pypi.org/project/nlopt | C/Python | MIT | MMA, CCSAQ, SLSQP, many more | updater | IMPORT; **cp314 win_amd64 wheel exists** | V |
| 85 | cyipopt 1.7.0 | https://pypi.org/project/cyipopt | Cython | EPL-2.0 | IPOPT interface | updater | IMPORT is hard: **PyPI has sdist only (no wheels, any release)** | V |
| 86 | pyOptSparse | https://github.com/mdolab/pyoptsparse | Python | LGPL-3.0 | Common wrapper over SNOPT, IPOPT, ParOpt, etc. | updater | **Not on PyPI** (conda-forge/source) | V |
| 87 | Svanberg MMA/GCMMA MATLAB | http://www.smoptit.se/ | MATLAB | GPL (asks for e-mail notification, citation) | Reference MMA | updater | BRIDGE / ORACLE | S |
| 88 | ceviche 0.1.3 | https://github.com/fancompute/ceviche | Python | MIT | FDFD/FDTD EM with autograd; photonic inverse design | physics (EM), problem | IMPORT (`pip install ceviche`, pure wheel) | V |
| 89 | ceviche-challenges | https://github.com/google/ceviche-challenges | Python | Apache-2.0 (repo archived) | Photonic inverse-design benchmark problems | problem/benchmark | MAKE; PyPI status UNVERIFIED | V (GitHub) |
| 90 | SPINS-B | https://github.com/stanfordnqp/spins-b | Python | GPL-3.0 | Photonic inverse design | physics (EM) | ORACLE; `spins` on PyPI 0.2.0 may be unrelated: U | V (GitHub) |

---

## Corrections to the catalogue

Rows refer to the slot READMEs in the worktree copy.

1. **JAX-FEM licence** (models README row "JAX-FEM ... Apache-2"): GitHub licence is **GPL-3.0** (API: `GPL-3.0`; PyPI licence text is the GPL, classifier says BSD, which is inconsistent). It is pip-installable (`jax-fem` 0.0.12, py>=3.12), but GPL-3 matters for any IMPORT.
2. **Volume-preserving Heaviside** (filters README, marked 📄): open code exists, so should be 🔗. top99neo/top3D125 (DTU) and topoptlab both implement it. See claim (b).
3. **PDE / Helmholtz filter** (filters README, marked 📄): open code exists. `top82.m` on the DTU top88 page is a drop-in 82-line PDE-filter variant, so it should be 🔗.
4. **Heaviside / morphology**: `top110.m` (DTU) is open Heaviside code; the morphology filters (Sigmund 2007) remain paper only (no public code found).
5. **TOFLUX** (models README): **no licence stated** anywhere in the repo. Wrapping or copying is not safe until the authors add one. AuTO is GPL-3.0; TOuNN is GPL-3.0.
6. **dl4to** (representations README): Apache-2.0 confirmed, but it is **not on PyPI** (the pip route is `pip install git+https://github.com/dl4to/dl4to`, pinning pyvista 0.38.1). Do not list as a plain `pip` dependency.
7. **neural-structural-optimization**: Apache-2.0 confirmed; **not pip-installable**, depends on TensorFlow + autograd (not JAX), NLopt for MMA.
8. **TOuNN link** is `http://www.ersl.wisc.edu/software/TOuNN.zip`; a GitHub repo `UW-ERSL/TOuNN` (GPL-3.0) exists and is the preferable link. The zip itself was not re-checked: UNVERIFIED.
9. **mmapy / MMA licence**: GPL-3.0 (derived from Svanberg's GPL MATLAB). Any updater plug-in built on it inherits GPL. `nlopt` (MIT) provides MMA/CCSAQ without that constraint, and has a cp314 Windows wheel.
10. **ToPy**: `pip install topy` fetches an unrelated "typo-fixer" project. ToPy is not pip-installable under that name.
11. **ParOpt** (updaters README): not on PyPI; LGPL-3 per docs. Not realistic for a Windows Python 3.14 user.
12. **Pointers missing from the catalogue (NEW)**: topoptlab (the biggest find), pytopo3d, scikit-topt, torch-fem, JaxSSO, SOPTX, PyHexTop/pygpto/PyTOPress, TopTMC, TopBuck250, tops140, top200EM, deHomTop808, TOP3D_XL, STORX (already cited only as an arXiv ID in the catalogue; repo `DEL-KU/storx` is MIT), Swan.
13. **Catalogue entry "Fibre orientation ... FRC-TOuNN"** has no link. FRC-TOuNN is arXiv 2205.03737; code repo not located: UNVERIFIED.
14. **TOBS "101-line MATLAB"** points to Springer doi 10.1007/s00158-020-02719-9; not fetched, UNVERIFIED that the code is in the supplement.
15. **Activity**: several entries are stale (ToPy last push 2022, zfergus/topopt 2022, MultiscaleTopOpt 2019, ceviche 2023, ceviche-challenges archived 2024).

## Verified claims (a)-(i)

**(a) The top88 paper includes a PDE-filter variant: TRUE.**
Evidence: paper PDF (Lirias copy) has section "4.2 Filtering based on Helmholtz type differential equations", states "The PDE filter requires minor changes of the 88 line code and reduces it to 82 lines", and the DTU page offers `top82.m`. It also notes the Heaviside projection cannot be directly applied with the PDE filter.

**(b) top99neo implements volume-preserving Heaviside: TRUE.**
Evidence: abstract (arXiv 2005.05436) "a volume-preserving density projection"; the downloaded `top99neo.m` computes the threshold eta by a Newton iteration (`if ft > 1 ... eta = eta - f/mean(deta(...))`, active for `ft == 3`). Note: eta is found by Newton, while the OC multiplier lambda uses bisection (an earlier phrase in the paper). Code carries an "authors reserve all rights" disclaimer, no open-source licence.

**(c) Sigmund's 99-line and top88 papers include compliant-mechanism and heat-conduction extensions: FALSE (no code in either).**
Evidence: the 88-line paper only says it "can be converted to a code for mechanism synthesis or for heat conduction problems" following Bendsoe & Sigmund 2003 (no implementation). The 99-line DTU page lists only multiple load cases, alternative filters, passive areas as student exercises. The code with compliant-mechanism and heat instructions is the 169-line top3d of Liu & Tovar (SMO 2014).

**(d) Ferrari, Sigmund & Guest 2021 published a ~250-line linearised-buckling MATLAB code: TRUE.**
"Topology optimization with linearized buckling criteria in 250 lines of Matlab", SMO 2021, doi 10.1007/s00158-021-02854-x, arXiv 2101.02973; code `topBuck250.m` on DTU (needs `fsparse`; no licence stated).

**(e) A "213-line" MATLAB code for geometrically nonlinear TO exists (SMO 2019): TRUE, with a catch.**
Chen, Zhang & Zhu, SMO 2019 (doi 10.1007/s00158-018-2138-5): density method with additive hyperelasticity, but FEA is done through **ANSYS APDL**, so it cannot run in plain MATLAB. Separate open-in-paper code: Han, Xu & Liu "137-line" BESO geometrically nonlinear (SMO 2021).

**(f) Deng et al. 2021 published a 146-line 3-D stress code: TRUE with qualification.**
Authors Hao Deng, Praveen S. Vulimiri, Albert C. To; arXiv 2104.01210: "146-line 3D sensitivity analysis code of stress-based topology optimization", p-norm stress, adjoint, MMA driver, FD verification. It is a sensitivity-analysis code with three example problems, not a full local-stress solver (PolyStress is the full local-stress one).

**(g) Wei, Li, Allaire & Wang 2018 published an 88-line parameterised level-set code: FALSE as stated (authorship wrong).**
The code exists: Peng Wei, Zuyu Li, Xueping Li, Michael Yu Wang, "An 88-line MATLAB code for the parameterized level set method based topology optimization using radial basis functions", SMO 58(2) 2018, 831-849. Allaire is not an author.

**(h) Licence and pip-installability**

| Item | Licence | pip? | Notes |
|------|---------|------|-------|
| Feppon null-space optimizer | GPL-3 | Yes: `nullspace_optimizer` 1.3.0, py>=3.9, pure wheel | gitlab.com/florian.feppon/null-space-optimizer |
| ParOpt | LGPL-3 (docs); GitHub NOASSERTION | **No** (not on PyPI) | C++/MPI/Cython, build from source |
| mmapy (Deetman) | GPL-3.0 | Yes: `mmapy` 0.3.1, py>=3.6 | MMA + GCMMA |
| AuTO | GPL-3.0 | No (Colab notebooks) | JAX |
| google-research neural-structural-optimization | Apache-2.0 | No | TF, autograd, NLopt |
| dl4to | Apache-2.0 | No on PyPI; `pip install git+https://...` | PyTorch |
| ceviche | MIT | Yes: `ceviche` 0.1.3 | ceviche-challenges: Apache-2.0, archived, PyPI UNVERIFIED |
| TOFLUX | none stated | No (`pip install -e .` from clone) | JAX/Flax/Optax |
| JAX-FEM | GPL-3.0 | Yes: `jax-fem` 0.0.12, py>=3.12 | PyPI classifier says BSD, contradicts |

**(i) Windows wheels for Python 3.14: nlopt TRUE, cyipopt FALSE.**
- `nlopt` 2.11.0 (uploaded 2026-07-17) lists `nlopt-2.11.0-cp314-cp314-win_amd64.whl` (also cp310-cp313).
- `cyipopt` 1.7.0 on PyPI is an **sdist only** (every release 1.3.0 to 1.7.0rc1 is sdist only), so no Windows wheel for any Python version. Installation needs Ipopt installed and a compiler, or conda-forge; whether conda-forge has a py3.14 build is UNVERIFIED.

## Count summary

Entries listed: 90 (some rows group 2-3 related codes). By primary slot:
- Whole method / framework: about 38
- Representation (level set, geometry, multiscale, IGA, truss, polygonal, neural, hex): about 22
- Physics / model / response (buckling, stress, nonlinear, contact, EM, fluid, thermal, pressure): about 14
- Updater (optimiser): about 12 (mmapy, nullspace-optimizer, ParOpt, NLopt, cyipopt, pyOptSparse, MMA MATLAB, OpenLSTO SLP, BESO, ABM, stochastic, PTO)
- Filter / schedule / interpolation: about 5 (top82, top110, top99neo, topoptlab, multi-material)
- Problem / benchmark: about 4 (neural-structural-optimization, ceviche-challenges, tops140, top200EM)

By route: IMPORT-able today on Windows Python 3.14: pymoto, topoptlab, pytopo3d, torch-fem, JaxSSO, jax-fem (needs JAX), mmapy, nullspace-optimizer, nlopt, ceviche. scikit-topt excluded (py<3.14). cyipopt excluded (no wheel).
