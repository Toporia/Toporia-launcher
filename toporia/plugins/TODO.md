# Integration to-do: every open topology-optimisation code

What is being brought into Toporia, **in order of effort, least first**. Each line becomes
one part, one passing `toporia check`, one row turned ✅ in its folder's README, and one
commit.

**How each one comes in:**

| Mark | Meaning |
| :-- | :-- |
| **IMPORT** | A Python package: `pip install` it and write a thin adapter. None of its code is rewritten. Declared with `dependencies = (...)`, so it is greyed out in the GUI where it is not installed. |
| **BRIDGE** | A MATLAB code run unchanged through the MATLAB Engine, as a whole method and as a test oracle. Not copied into this repository; the user points Toporia at their own copy. |
| **MAKE** | Written here, from the paper or by porting a short code. The original, where it exists, is the oracle the test compares against. |
| **ORACLE** | Not integrated: run outside on the same problem, and a test compares the results. |

Status: `[ ]` to do · `[~]` an agent is on it · `[x]` merged and verified.
The verified survey of every open code found is [SURVEY.md](SURVEY.md). Lines marked *(unverified)* are from memory and still have to be found and checked by the
survey (wave 0).

---

## Wave 0: the survey

- [ ] Search systematically for every open TO code (GitHub, SMO educational articles, arXiv
      2015–2026, Zenodo), check every link, record language, licence, what it implements and
      which Toporia slot it fits. Extend this list and fix the catalogue's 🔗/📄 markers.

## Wave 1: IMPORT, Python packages (connector only)

Watch out for Python 3.14: some of these have no wheels for it yet. The agent checks this
first, and if a package will not install, reports it rather than working around it.

| | Package | Slot | Gives | Licence |
| :-- | :-- | :-- | :-- | :-- |
| [x] | SciPy `trust-constr`, `COBYLA`, … (already a dependency) | updater | more constrained optimisers in the `scipy_slsqp` pattern | BSD |
| [x] | NLopt | updater | MMA, CCSA, SLSQP, augmented Lagrangian, COBYLA, … in one wrapper | LGPL/MIT |
| [ ] | cyipopt (IPOPT) | updater | interior point | EPL. **Blocked 2026-10-11:** no Windows wheel for Python 3.14; a source build needs pkg-config + IPOPT. Needs conda-forge or an older Python |
| [ ] | mmapy, Deetman's MMA/GCMMA Python port | updater + oracle for `mma.py` | the reference MMA | GPL-3 *(check; GPL means optional only)* |
| [ ] | Feppon's null-space optimizer | updater | constrained optimiser for level-set and shape problems | *(unverified)* |
| [ ] | ParOpt | updater | interior point built for TO | LGPL *(unverified)* |
| [ ] | pyMOTO, thermal / dynamics / mechanism modules | model | heat, eigenfrequency, compliant mechanism on our grids | MIT |
| [ ] | dl4to + the SELTO datasets | problems | 3-D benchmark problems with reference solutions | *(check)* |
| [ ] | JAX (+ AuTO, Chandrasekhar et al.) | model / representation | automatic differentiation for new responses, neural fields | Apache-2 / *(check)* |
| [ ] | PyTorch or JAX for TOuNN (Chandrasekhar & Suresh) | representation + Adam updater | neural reparameterisation | *(check)* |
| [ ] | google-research `neural-structural-optimization` (Hoyer et al.) | problems + representation | ~100 benchmark problems, neural reparameterisation | Apache-2 |
| [ ] | ceviche | model | photonics (FDFD) on a grid | MIT |
| [ ] | JAX-FEM | model | non-linear materials, GPU | GPL-3 *(optional only)* |
| [ ] | TOFLUX | model | fluids (JAX) | *(check)* |
| [ ] | ToPy, PyTopo3D, zfergus/topopt, Lagerweij/topopt | oracle | independent 2-D/3-D SIMP results | MIT / CC-BY / *(check)* |
| [ ] | FEniTop, Firedrake + pyadjoint, Meep | model | unstructured meshes, real geometry | Linux/WSL only; after the unstructured-mesh change |

## Wave 2: BRIDGE, MATLAB codes run unchanged

**Blocked 2026-10-11:** the MATLAB Engine for R2026a supports Python ≤ 3.13 only (engine 26.2 = R2026b is the first for 3.14). Options: a Python 3.13 environment, MATLAB R2026b, or a `matlab -batch` subprocess bridge (final result only). Waiting for the user's choice.

One generic bridge first (MATLAB Engine for Python, `dependencies = ("matlab.engine",)`),
then each code is a small wrapper that hands it our mesh size, loads, supports and volume.
Each comes in as a **whole method** (it cannot be split into parts) and as the **oracle** for
the matching MAKE item below.

| | Code | Oracle for |
| :-- | :-- | :-- |
| [ ] | top88 (Andreassen et al. 2011), incl. its PDE-filter variant | `q4` + OC, density filter, PDE filter |
| [ ] | top99neo (Ferrari & Sigmund 2020) | volume-preserving Heaviside, continuation |
| [ ] | top3d (Liu & Tovar 2014) / top3D125 (Ferrari & Sigmund 2020) | `h8` |
| [ ] | Svanberg MMA / GCMMA | `mma.py` |
| [ ] | 88-line RBF level set (Wei, Li, Li & Wang, SMO 2018) | `levelset_rbf.py` |
| [ ] | 88-line reaction–diffusion level set (Otomori et al. 2015) | RD level set |
| [ ] | 129-line level set (Challis 2010) | HJ level set |
| [ ] | TOBS 101-line (Picelli et al. 2021) | TOBS updater |
| [ ] | MMC88 / MMC188 (Zhang et al. 2016) | `mmc.py`, variable thickness |
| [ ] | GGP-Matlab, GPTO (Norato et al.) | geometry projection |
| [ ] | Langelaar AM filter | `am.py` |
| [ ] | 250-line buckling (Ferrari, Sigmund & Guest 2021) | buckling |
| [ ] | 213-line geometrically non-linear (SMO 2019) *(unverified)* | finite strain |
| [ ] | 115-line alternating active-phase multi-material (Tavakoli & Mohseni 2014) | multi-material |
| [ ] | PolyStress (Giraldo-Londoño & Paulino 2021) | local stress + AL |
| [ ] | topflow (Alexandersen 2023) | fluids |
| [ ] | 146-line 3-D stress (Deng et al. 2021) *(unverified)* | stress in 3-D |
| [ ] | top3d (Liu & Tovar 2014) mechanism and heat instructions (the survey found that the 99-line/top88 papers do not include them) | mechanism, heat |

## Wave 3: MAKE, small (one file in an existing slot)

| | Part | Slot | Source |
| :-- | :-- | :-- | :-- |
| [x] | PDE / Helmholtz filter | filter | Lazarov & Sigmund 2011; top88 |
| [x] | Volume-preserving Heaviside | filter | Xu, Cai & Cheng 2010; top99neo |
| [ ] | Morphology: erode, dilate, open, close | filter | Sigmund 2007 |
| [ ] | Anisotropic PDE filter | filter | Lazarov & Sigmund 2011 |
| [ ] | Extrusion, pattern repetition, casting direction | filter | Ishii & Aomura 2004; Bendsøe & Sigmund 2003; Xia et al. 2010 |
| [~] | SINH, ordered SIMP, Hashin–Shtrikman | interpolation (ordered SIMP done; SINH and HS need the material law to see the volume response and ν) | Bruns 2005; Zuo & Saitou 2017; Bendsøe & Sigmund 1999 |
| [ ] | Convergence-triggered continuation, continuation-free projection | schedule | Wang et al. 2011; Guest et al. 2011 |
| [ ] | Grey level over the run, smoothed outlines | post-processor | Sigmund 2007; Subedi et al. 2020 |
| [ ] | TOBS (integer LP via `scipy.optimize.milp`) | updater | Picelli et al. 2021 |
| [ ] | CONLIN, multi-constraint OC | updater | Fleury 1989; Zhou & Rozvany 1991 |
| [ ] | Adam, proportional TO, simulated annealing | updater | Kingma & Ba 2015; Biyikli & To 2015 |
| [ ] | Hard-kill BESO, floating projection | updater | Huang & Xie 2010; Huang 2021 |
| [ ] | Variable-thickness MMC, MMV, B-spline fields | representation | Zhang et al. 2016, 2017; Qian 2013 |
| [ ] | L-bracket, force inverter | problem | Duysinx & Bendsøe 1998; Sigmund 1997 |
| [ ] | Robust three-field preset (variants over `heaviside.eta`) | preset | Wang, Lazarov & Sigmund 2011 |
| [ ] | Compliant mechanism (output displacement, uses `adjoint()`) | response | Sigmund 1997 |

## Wave 4: MAKE, medium (new physics feature group or whole method)

- [ ] Heat conduction physics + thermal compliance
- [ ] Eigenproblem feature group → eigenfrequency, then linearised buckling
- [ ] Harmonic response
- [ ] Local stress + augmented Lagrangian updater
- [ ] Geometry projection representation
- [ ] Reaction–diffusion level set; Hamilton–Jacobi level set; topological derivative
- [ ] Phase field
- [ ] Explicit length-scale constraints; machining accessibility; Gaynor self-support
- [ ] Multi-resolution design and analysis meshes
- [ ] Geometrically non-linear elasticity

## Wave 5: framework changes, then what they unlock

- [ ] Several fields per element → DMO, fibre orientation, multi-material
- [ ] Unstructured meshes → PolyTop/PolyMesher, VEM, FEniTop, CAD import
- [ ] Beam/truss elements → ground structure (GRAND)
- [ ] Multiscale / de-homogenisation; IGA; CutFEM
- [ ] Fluids, transient, acoustics, photonics at full scale
- [ ] Generative models (TopoDiff, TopologyGAN) on the datasets above

## Not planned

Fracture, fatigue, crashworthiness, residual stress: research problems, not ports. Julia and
C++ engines (GridapTopOpt.jl, TopOpt.jl, TopOpt_in_PETSc, MOOSE, OpenLSTO) stay oracles.
