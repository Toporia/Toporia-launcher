# Methods — how the design is described

A method owns the design variables and turns them into a density field. Most are not
written by hand: a method is named `"<model>+<updater>"` and **built on demand** from any
[model](../models/README.md) and any [updater](../updaters/README.md), so there is nothing
to declare per pairing. A method that does not split that way — the RBF level set, which
evolves its own representation with its own volume control — implements
[`core.contract.OptimizationMethod`](../../core/contract.py) directly.

This is the layer that decides which shapes are reachable at all. Everything below is a
different answer to "what *is* the design?".

**Status: 15 selectable in Toporia · 14 with open code · 3 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Selectable now. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

**14 pairings**, every model with every updater — `2 models × 7 updaters`:

| | [`oc`](../updaters/oc.py) | [`mma`](../updaters/mma.py) | [`simpl`](../updaters/simpl.py) | [`beso`](../updaters/beso.py) | `pymoto_mma` | `pymoto_gcmma` | [`scipy_slsqp`](../updaters/scipy_slsqp.py) |
| :-- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| [`q4`](../models/q4.py) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| [`pymoto_elastic`](../models/pymoto_elastic.py) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**1 whole method**, which does not split into parts:

| Method | File | Name | Reference |
| :-- | :-- | :-- | :-- |
| ✅ RBF level set | [`levelset_rbf.py`](levelset_rbf.py) | `levelset` | Wang & Wang, *CMAME* 2006 |

Older names are still accepted and expand through `PRESETS` in
[`__init__.py`](__init__.py): `density` → `q4+oc`, `density_mma` → `q4+mma`,
`density_simpl` → `q4+simpl`, `beso` → `q4+beso`, `density_gcmma` →
`q4+pymoto_gcmma`, `pymoto` → `pymoto_elastic+pymoto_mma`.

Three of the field's parameterisation families are therefore covered: **density/SIMP**
(both models), **parameterised level set** (`levelset`), and the **discrete evolutionary**
family (`beso`). The families below are not.

## Candidates — density and discrete

| Family | Status | Reference | What it adds |
| :-- | :-- | :-- | :-- |
| RAMP interpolation | 📄 | Stolpe & Svanberg, *SMO* 2001 | Rational interpolation with non-vanishing sensitivity at ρ=0. Better behaved for design-dependent loads and some non-linear problems, and a prerequisite for pressure loads. Our SIMP law is hard-coded in [`fe/q4_plane_stress.py`](../fe/q4_plane_stress.py); making the interpolation a choice is a small change and a real comparison axis. |
| Homogenisation | 📄 | Bendsøe & Kikuchi, *CMAME* 1988 | The original formulation: microstructure density and orientation as variables. Now mainly a route into multiscale work. |
| TOBS — binary + integer programming | 🔗 [101-line MATLAB](https://link.springer.com/article/10.1007/s00158-020-02719-9) | Sivapuram & Picelli 2018; Picelli et al., *SMO* 2021 | Strictly {0,1} variables with several constraints handled explicitly. Needs the ILP updater in [`updaters/`](../updaters/README.md). |
| Multi-material | 🔗 [PolyMat](https://dl.acm.org/doi/abs/10.1007/s00158-018-2094-0) | Stegmann & Lund 2005 (DMO); Tavakoli & Mohseni, *SMO* 2014; Zuo & Saitou, *SMO* 2017 (ordered SIMP) | Three competing schemes: ordered SIMP (one variable, cost-scaled), DMO/SFP (one variable per material), alternating active phase (a sequence of two-phase problems). |
| Multiscale, lattice infill, de-homogenisation | 🔗 [MultiscaleTopOpt](https://github.com/LLNL/MultiscaleTopOpt) | Groen & Sigmund, *IJNME* 2018; Groen et al., *CMAME* 2020; review: Wu, Sigmund & Groen, *SMO* 2021 | Optimise a coarse density-and-orientation field with homogenised properties, then project it to a fine single-scale structure. Three orders of magnitude cheaper than resolving the lattice. Related: shell/coating (Clausen et al. 2015), bone-like infill (Wu et al. 2018). |

## Candidates — level set and implicit

| Family | Status | Reference | What it adds |
| :-- | :-- | :-- | :-- |
| Hamilton–Jacobi level set | 🔗 Challis 129-line MATLAB (with the paper), [OpenLSTO](https://github.com/M2DOLab/OpenLSTO), [GridapTopOpt.jl](https://github.com/zjwegert/GridapTopOpt.jl) | Wang, Wang & Guo, *CMAME* 2003; Allaire, Jouve & Toader, *JCP* 2004; Challis, *SMO* 2010 | The classical form: boundary advected by a shape-derivative velocity. Crisp interfaces, but cannot nucleate holes in 2-D unaided and needs re-initialisation. |
| Reaction–diffusion level set | 🔗 [MATLAB code](https://link.springer.com/article/10.1007/s00158-014-1190-z) | Yamada, Izui, Nishiwaki & Takezawa, *CMAME* 2010; Otomori et al., *SMO* 2015 | Level set evolved by a reaction–diffusion equation whose reaction term is the topological derivative. **Nucleates holes, needs no re-initialisation, one length-scale knob** — the most attractive level-set variant to add next to our RBF method. |
| Topological derivative | 🔗 [FreeFEM code](https://link.springer.com/article/10.1007/s00158-023-03529-5) | Sokołowski & Żochowski, *SICON* 1999; Amstutz & Andrä, *JCP* 2006; Novotny et al., *SMO* 2023 | The exact first-order sensitivity to inserting an infinitesimal hole. Stands alone, or supplies nucleation to a level-set scheme. |
| Phase field | 📄 | Bourdin & Chambolle, *ESAIM:COCV* 2003; Takezawa, Nishiwaki & Kitamura, *JCP* 2010 | Cahn–Hilliard / Allen–Cahn energy with a double-well potential: the perimeter penalty is intrinsic, so **no filter is needed at all**. Couples naturally to phase-field fracture. |

## Candidates — explicit geometry

| Family | Status | Reference | What it adds |
| :-- | :-- | :-- | :-- |
| MMC / MMV — moving morphable components and voids | 🔗 MMC188, MMC3D256 (with the papers) | Guo, Zhang & Zhong, *JAM* 2014; Zhang et al., *SMO* 2016; Zhang et al. 2017 | Explicit bars and blobs whose position, length, thickness and angle are the only variables: a few hundred instead of a million, and CAD-ready geometry by construction. |
| Geometry projection / feature mapping | 🔗 [GPTO](https://github.com/jnorato/GPTO), [GGP](https://github.com/topggp/GGP-Matlab) | Norato et al., *CMAME* 2015; Smith & Norato, *SMO* 2020; review: Wein, Dunning & Norato, *SMO* 2020 | A high-level geometric description (bars, plates, primitives, NURBS) smoothly projected onto a fixed analysis grid, so real geometric features can be constrained directly. |
| Ground structure / truss layout | 🔗 [GRAND, GRAND3](https://paulino.princeton.edu/journal_papers/2014/SMO_14_GRAND.pdf) | Michell 1904; Zegard & Paulino, *SMO* 2014, 2015; He, Gilbert et al., *SMO* 2019 | A dense candidate bar network sized by LP/NLP. **A genuinely different design space from a density field**, converging to Michell layouts; the natural formulation for frames. |
| Isogeometric TO | 🔗 IgaTop (with the paper) | Gao et al. (IgaTop) | NURBS basis shared by geometry, analysis and density: no re-meshing, smooth boundaries straight into CAD. |
| Stiffness spreading | 🔗 [SSM](https://github.com/PengWeiScut/SSM) | Wei et al. 2010 | Explicit-geometry precursor to the projection methods above. |

## Candidates — learned parameterisations

Three genuinely different things, which fail in different ways. Only the first belongs in
this folder; the other two are listed in [`models/`](../models/README.md) and for context.

| Family | Status | Reference | What it adds |
| :-- | :-- | :-- | :-- |
| Neural reparameterisation | 🔗 [TOuNN](http://www.ersl.wisc.edu/software/TOuNN.zip) | Hoyer, Sohl-Dickstein & Greydanus 2019; Chandrasekhar & Suresh, *SMO* 2021; Jain & Suresh, *Eng. Comput.* 2023 (DMF-TONN) | The density field **is** a network: weights are the design variables, the FE solver stays in the loop, no training data, and the result is still physically feasible. Mesh-independent and resolution-free. The safest learned method to add, and it needs the Adam updater. |
| Direct generation (GAN, diffusion) | 🔗 [nn4topopt](https://github.com/ISosnovik/nn4topopt), [dl4to](https://github.com/dl4to/dl4to) | Sosnovik & Oseledets 2019; Nie et al., *JMD* 2021 (TopologyGAN); Mazé & Ahmed, *AAAI* 2023 (TopoDiff) | Maps boundary conditions straight to a structure. Fast and genuinely multi-candidate — what "generative design" promises — but constraint satisfaction and out-of-distribution behaviour are unsolved. Needs a trained model and the datasets in [`problems/`](../problems/README.md). |
| Online surrogate | 🔗 [SOLO](https://github.com/deng-cy/deep_learning_topology_opt) | Deng et al. 2022 | Trains the surrogate during the optimisation instead of on a pre-built dataset. |

## References

- M. P. Bendsøe, O. Sigmund, *Topology Optimization: Theory, Methods and Applications*, Springer 2003.
- O. Sigmund, K. Maute, "Topology optimization approaches: a comparative review", *SMO* 48 (2013) 1031–1055.
- J. D. Deaton, R. V. Grandhi, "A survey of structural and multidisciplinary continuum topology optimization", *SMO* 49 (2014) 1–38.
- S. Wein, P. D. Dunning, J. A. Norato, "A review on feature-mapping methods for structural optimization", *SMO* 62 (2020) 1597–1638.
- X. Huang, "Open-source codes of topology optimization: a summary for beginners", *CMES* 137 (2023) — the survey these tables were built from.
