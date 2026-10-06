# Filters — regularisation, projection and fabrication rules

A filter maps design variables to physical densities and carries the chain rule back
again: `forward(x)`, `backward(x_in, sensitivity)`. They compose into an ordered
[`FilterChain`](../../framework/parts/filter.py), so a run can stack a density filter, a projection and a
fabrication rule and get consistent sensitivities through all three.

Without a filter, a density method produces checkerboards and a mesh-dependent result.
This layer is not optional decoration — it is what makes the problem well posed.

**Status: 6 in Toporia · 1 with open code · 15 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here, registered, tested. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Filter | File | Registry name | Reference |
| :-- | :-- | :-- | :-- |
| ✅ Density filter | [`filter_density.py`](density.py) | `density` | Bruns & Tortorelli, *CMAME* 2001; Bourdin, *IJNME* 2001 |
| ✅ Sensitivity filter | [`filter_sensitivity.py`](sensitivity.py) | `sensitivity` | Sigmund, *Struct. Optim.* 1997 |
| ✅ Heaviside projection, free threshold η | [`filter_heaviside.py`](heaviside.py) | `heaviside` | Guest et al., *IJNME* 2004; `tanh` form from Wang, Lazarov & Sigmund, *SMO* 2011 |
| ✅ AM overhang filter | [`filter_am.py`](am.py) | `am` | Langelaar, *Addit. Manuf.* 2016; *SMO* 2017 |
| ✅ Symmetry filter | [`filter_symmetry.py`](symmetry.py) | `symmetry` | standard practice |
| ✅ Routing radius filter | [`filter_routing.py`](routing.py) | `routing` | Toporia-specific |

The projection already takes an arbitrary threshold η, which is the prerequisite for the
robust formulation below.

## Candidates — regularisation

| Filter | Status | Reference | Why it matters |
| :-- | :-- | :-- | :-- |
| PDE / Helmholtz filter | 📄 | Lazarov & Sigmund, *IJNME* 86 (2011) 765–781 | Filtering as a solve of `−r²∇²ρ̄ + ρ̄ = ρ̃` with Neumann boundaries. No neighbour lists and no stored weight matrix, so memory is constant in the radius, it scales to distributed memory, and **it is the only density filter that transfers to unstructured meshes and 3-D** — which matters now that a pyMOTO model exists. Our [`filter_density.py`](density.py) builds an n×n weight matrix in a four-deep Python loop, the slowest part of starting a fine run. |
| Morphology filters: erode, dilate, open, close | 📄 | Sigmund, *SMO* 33 (2007) 401–424 | Smooth min/max filters that give genuinely black-and-white designs and enforce feature size directly. The smooth min/max machinery already exists in [`filter_am.py`](am.py). |
| Volume-preserving Heaviside | 📄 | Xu, Cai & Cheng, *SMO* 41 (2010) 495–505 | Adjusts η each iteration so projection does not change the volume. About twenty lines on the existing filter. |
| Anisotropic / directional filters | 📄 | Lazarov & Sigmund 2011 (PDE form) | Different length scales per direction, for rolled or printed material. Falls out of the PDE filter almost free. |
| Multi-resolution design and analysis meshes | 📄 | Nguyen, Paulino, Song & Le, *SMO* 2010; Groen et al., *IJNME* 2017 | Fine density field over a coarse FE mesh. Large speed-ups, with a known risk of artificial fine-scale artefacts. |

## Candidates — length scale

| Filter / formulation | Status | Reference | Why it matters |
| :-- | :-- | :-- | :-- |
| Robust three-field formulation | 📄 | Sigmund, *Acta Mech. Sinica* 2009; Wang, Lazarov & Sigmund, *SMO* 43 (2011) 767–784 | **The most practically important formulation in density-based TO.** Optimise the worst of eroded / intermediate / dilated designs (η > 0.5, 0.5, < 0.5): minimum member size *and* minimum cavity size, results that converge under mesh refinement, and tolerance to over- and under-etching. Costs three FE solves per iteration. It is also what makes an AM-filtered result trustworthy, since one-element-wide members are not printable whatever the overhang filter says. Not strictly a filter — it wraps a Model. |
| Explicit geometric length-scale constraints | 📄 | Guest, *SMO* 2009; Zhou, Lazarov, Wang & Sigmund, *CMAME* 2015 | Imposes minimum length scale as constraints on the filtered fields, avoiding the three-fold cost of the robust formulation. Needs a second constraint slot — see [`updaters/`](../updaters/README.md). |
| Hyperparameter-free minimum length scale | 📄 | [arXiv:2507.16108](https://arxiv.org/abs/2507.16108) (2025) | Recent attempt to remove the tuning that the formulations above require. |

## Candidates — fabrication

The AM overhang filter is implemented. Everything else in this table is a manufacturing
rule Toporia cannot yet express, and this is where commercial "generative design" tools
actually differentiate.

| Rule | Status | Reference | Why it matters |
| :-- | :-- | :-- | :-- |
| Projection-based self-support | 📄 | Gaynor & Guest, *SMO* 2016 | An alternative overhang treatment to Langelaar's layer-wise filter; worth having both to compare. |
| Enclosed void / powder removal | 📄 | Li et al., *SMO* 2016; Liu et al. 2015 | A virtual temperature field that only heats up inside disconnected voids, penalised to zero. Cheap and elegant. |
| Casting and moulding directionality | 📄 | Xia, Shi, Wang & Liu, *CMAME* 2010; Guest & Zhu 2012 | No undercuts relative to a parting direction: a monotone projection along the draw axis. |
| Machining accessibility | 📄 | Langelaar, *CAD* 2019; Lee, Nomura & Dede 2020 | Every solid point reachable by a tool from an allowed set of directions. A generalisation of the AM filter's directional sweep. |
| Extrusion / 2.5-D milling | 📄 | Ishii & Aomura 2004 | Density constant along one axis — structurally the same operator as [`filter_symmetry.py`](symmetry.py). |
| Pattern repetition | 📄 | Bendsøe & Sigmund, *Topology Optimization*, Springer 2003 | Folds the design onto a repeating unit. Same machinery as the symmetry filter. |
| Residual stress / distortion aware | 📄 | Allaire & Jakabčin 2018; Miki & Yamada, *FEAD* 2021 | An inherent-strain model of the build inside the loop, so the *printed* shape is optimised rather than the designed one. |
| Fibre orientation for composites | 🔗 FRC-TOuNN | Chandrasekhar, Sridhara & Suresh, *CAD* 2022 | Continuous fibre angle alongside density; the angle field itself needs regularising for printable tow paths. |

## References

- T. E. Bruns, D. A. Tortorelli, "Topology optimization of non-linear elastic structures and compliant mechanisms", *CMAME* 190 (2001) 3443–3459.
- O. Sigmund, "Morphology-based black and white filters for topology optimization", *SMO* 33 (2007) 401–424.
- B. S. Lazarov, O. Sigmund, "Filters in topology optimization based on Helmholtz-type differential equations", *IJNME* 86 (2011) 765–781.
- F. Wang, B. S. Lazarov, O. Sigmund, "On projection methods, convergence and robust formulations in topology optimization", *SMO* 43 (2011) 767–784.
- M. Langelaar, "An additive manufacturing filter for topology optimization of print-ready designs", *SMO* 55 (2017) 871–883.
