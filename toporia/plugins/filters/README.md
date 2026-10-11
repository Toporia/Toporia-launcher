# Filters — regularisation, projection and fabrication rules

A filter maps design variables to physical densities and carries the chain rule back
again: `forward(x)`, `backward(x_in, sensitivity)`. They compose into an ordered
[`FilterChain`](../../framework/parts/filter.py), so a run can stack a density filter, a projection and a
fabrication rule and get consistent sensitivities through all three.

Without a filter, a density method produces checkerboards and a mesh-dependent result.
This layer is not optional decoration — it is what makes the problem well posed.

**In 3-D** (a scenario with a depth): the density, PDE, sensitivity, Heaviside, morphology, extrusion, pattern and casting filters work;
the AM overhang, routing and symmetry filters are written for plane problems and are refused
on a 3-D one, with the filters that can.

**Status: 12 in Toporia · 1 with open code · 9 paper only**

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
| ✅ PDE / Helmholtz filter (open code: top82.m) | [`pde.py`](pde.py) | `pde` | Lazarov & Sigmund, *IJNME* 86 (2011) 765–781; Andreassen et al., *SMO* 43 (2011) |
| ✅ Volume-preserving Heaviside (open code: top99neo) | [`heaviside.py`](heaviside.py), `eta_mode = volume_preserving` | `heaviside` | Xu, Cai & Cheng, *SMO* 41 (2010) 495–505; Ferrari & Sigmund, *SMO* 62 (2020) |
| ✅ AM overhang filter | [`filter_am.py`](am.py) | `am` | Langelaar, *Addit. Manuf.* 2016; *SMO* 2017 |
| ✅ Symmetry filter | [`filter_symmetry.py`](symmetry.py) | `symmetry` | standard practice |
| ✅ Routing radius filter | [`filter_routing.py`](routing.py) | `routing` | Toporia-specific |
| ✅ Morphology filters: erode, dilate, open, close | [`morphology.py`](morphology.py) | `morphology` | Sigmund, *SMO* 33 (2007) 401–424 |
| ✅ Extrusion (constant cross-section) | [`extrusion.py`](extrusion.py) | `extrusion` | Ishii & Aomura, *JSME Int. J.* 47 (2004) |
| ✅ Pattern repetition | [`pattern.py`](pattern.py) | `pattern` | Bendsøe & Sigmund, *Topology Optimization*, Springer 2003; Almeida, Paulino & Silva, *SMO* 39 (2009) |
| ✅ Casting (no undercuts) | [`casting.py`](casting.py) | `casting` | Gersborg & Andreasen, *SMO* 44 (2011) 875–881; Xia et al., *CMAME* 2010 |

The projection already takes an arbitrary threshold η, which is the prerequisite for the
robust formulation below.

## The PDE filter

[`pde.py`](pde.py) smooths the design by solving `−r²∇²ρ̄ + ρ̄ = ρ` with Neumann
boundaries on the design mesh (Q4 in 2-D, H8 in 3-D), with `r = rmin / (2√3)`. The FE
matrix is assembled and factorised once; each iteration is one back-substitution, and
`backward` is the exact adjoint (the operator is symmetric). It uses the same `rmin` as the
density filter, so the two compare directly: on the MBB beam with `q4+oc` at `rmin = 3`
the compliances are close. A constant field passes through unchanged and volume is
conserved. Like the density filter it does not treat passive elements specially. It is the
route to anisotropic filters and unstructured meshes.

- Paper: Lazarov & Sigmund, *IJNME* 86 (2011) 765–781. Code: the PDE section of the top88 paper
  (Andreassen et al., *SMO* 43 (2011)) and DTU's open `top82.m`.
- GUI: pick **PDE (Helmholtz) filter** in the filter list.
- Solver config: `"filter_specs": [{"type": "pde", "rmin": 3.0}]`.
- CLI: `toporia run "MBB Beam" --set method=q4+oc --set 'filter_specs=[{"type": "pde", "rmin": 3.0}]'`

## Volume-preserving Heaviside

The Heaviside projection normally uses a fixed threshold η, which shifts the volume as β
grows. With `eta_mode = "volume_preserving"` the filter solves for η on every forward pass
(bisection) so the projected mean density equals the input's, and the backward pass includes
the derivative of η with respect to the input, so the gradient stays exact. The default
(`"fixed"`) is unchanged.

- Papers: Xu, Cai & Cheng, *SMO* 41 (2010) 495–505; Ferrari & Sigmund, *SMO* 62 (2020) (open code: `top99neo.m`).
- GUI: choose **Threshold mode: Volume preserving** on the Heaviside filter.
- Solver config: `{"type": "heaviside", "eta_mode": "volume_preserving"}` after the density filter.
- CLI: `toporia run "MBB Beam" --set 'filter_specs=[{"type": "density"}, {"type": "heaviside", "eta_mode": "volume_preserving"}]'`

## Morphology filters

[`morphology.py`](morphology.py) replaces the density filter's weighted *mean* with a smooth
*minimum* (erode: a point stays solid only if its whole neighbourhood is) or a smooth
*maximum* (dilate: a point turns solid if any neighbour is). **Open** (erode, then dilate)
removes solid members thinner than the radius; **close** (dilate, then erode) fills voids
thinner than the radius. One filter, a `mode` option picks the operation. The neighbourhood is
the density filter's cone of radius `rmin`; `beta` sets the sharpness (small is nearly the
plain average, large is a hard min/max). A constant field passes through unchanged, and
`backward` is the exact adjoint. `beta` can be scheduled, so a geometric schedule on
`filters[1].beta` continues it, as for Heaviside.

Use it behind a density filter when you want a length scale imposed on one phase only
(minimum member size with open, minimum cavity size with close) instead of the symmetric
blur of the density filter. On the MBB beam (`q4+oc`, density `rmin = 3`, 150 iterations) a
`close`/`erode` after the density filter costs a few percent of compliance (about 410 to 450
against 405) and, without a long β continuation, does not by itself make the design blacker;
it shapes feature size rather than binarising, so combine it with Heaviside if you want 0/1.

- Paper: Sigmund, *SMO* 33 (2007) 401–424, [doi:10.1007/s00158-006-0087-x](https://doi.org/10.1007/s00158-006-0087-x).
- GUI: pick **Morphology filter** in the filter list, then the operation, radius and β.
- Solver config: `"filter_specs": [{"type": "density", "rmin": 3.0}, {"type": "morphology", "rmin": 2.0, "beta": 16.0, "mode": "close"}]`.
- CLI: `toporia run "MBB Beam" --set method=q4+oc --set 'filter_specs=[{"type": "density", "rmin": 3.0}, {"type": "morphology", "rmin": 2.0, "beta": 16.0, "mode": "close"}]'`

## Extrusion, pattern repetition and casting

Three manufacturing rules that are cheap to impose on a density field. The first two are
averages over a set of elements broadcast back — the same linear, self-adjoint operator as
[`symmetry.py`](symmetry.py) — and the third is a directional sweep in the spirit of
[`am.py`](am.py). None treats passive or void elements specially (as the symmetry filter
does not): the model re-imposes them on the physical density afterwards. All three work in
2-D and 3-D, and go after the density filter in the chain.

### Extrusion

[`extrusion.py`](extrusion.py) makes the density constant along one axis: each line of
elements parallel to it carries the line's mean (forward = average and broadcast, backward =
the same operation, its exact adjoint). Use it in 3-D for a part of constant cross-section
(an extruded or rolled profile). In 2-D, "constant along x" means a design made of
full-length strips and "constant along y" of full-height columns — rarely a good structure,
but it is the cross-section of the 3-D idea and handy for teaching.

- Paper: Ishii & Aomura, "Topology optimization for the extruded three dimensional structure
  with constant cross section", *JSME Int. J. Series A* 47 (2004) 198–206.
- GUI: pick **Extrusion (constant cross-section)** in the filter list and choose the axis.
- Solver config: `"filter_specs": [{"type": "density"}, {"type": "extrusion", "axis": "z"}]`
  (`z` needs a 3-D problem).
- CLI: `toporia run "MBB Beam" --set method=q4+oc --set 'filter_specs=[{"type": "density"}, {"type": "extrusion", "axis": "y"}]'`

### Pattern repetition

[`pattern.py`](pattern.py) folds the domain into `nx × ny (× nz)` identical cells: elements
at the same place in their cell share one density, their mean. Use it for repeating
structures (a truss bay, a lattice unit). The element count along each axis must divide by
the number of repeats; otherwise setup refuses with an error naming the axis and count
(cells of unequal size would not be identical, and dropping a remainder would change the
problem) — adjust the mesh resolution or the domain length.

- Papers: Bendsøe & Sigmund, *Topology Optimization: Theory, Methods and Applications*,
  Springer 2003; Almeida, Paulino & Silva, *SMO* 39 (2009) 359–371.
- GUI: pick **Pattern repetition** and set the repeats in x, y (and z).
- Solver config: `"filter_specs": [{"type": "density"}, {"type": "pattern", "nx": 2, "ny": 1}]`
- CLI: `toporia run "MBB Beam" --set method=q4+oc --set 'filter_specs=[{"type": "density"}, {"type": "pattern", "nx": 2}]'`

### Casting (no undercuts)

[`casting.py`](casting.py) keeps the design castable in a one-piece mould: along the draw
direction the density may only decrease, away from the parting plane. It is the running
minimum along each line, smoothed (`ρ_k = smin(x_k, ρ_{k−1})`) so the gradient is exact,
by one reverse sweep. The output is monotone to within √ε/2 = 5·10⁻⁴ (the smoothing).
`"+y"` means the mould is drawn off toward +y, so the parting plane is the low-y face; `-y`
the reverse; likewise x, and z in 3-D. This is the cumulative smooth-minimum form of the
explicit casting parameterisation, not Xia et al.'s level-set formulation.

- Papers: Gersborg & Andreasen, "An explicit parameterization for casting constraints in
  gradient driven topology optimization", *SMO* 44 (2011) 875–881; Xia, Shi, Wang & Liu,
  *CMAME* 2010.
- GUI: pick **Casting (no undercuts)** and choose the draw direction.
- Solver config: `"filter_specs": [{"type": "density"}, {"type": "casting", "direction": "+y"}]`
- CLI: `toporia run "MBB Beam" --set method=q4+oc --set 'filter_specs=[{"type": "density"}, {"type": "casting", "direction": "+y"}]'`

## Candidates — regularisation

| Filter | Status | Reference | Why it matters |
| :-- | :-- | :-- | :-- |
| Anisotropic / directional filters | 📄 | Lazarov & Sigmund 2011 (PDE form) | Different length scales per direction, for rolled or printed material. Falls out of the PDE filter almost free. |
| Multi-resolution design and analysis meshes | 📄 | Nguyen, Paulino, Song & Le, *SMO* 2010; Groen et al., *IJNME* 2017 | Fine density field over a coarse FE mesh. Large speed-ups, with a known risk of artificial fine-scale artefacts. |

## Candidates — length scale

| Filter / formulation | Status | Reference | Why it matters |
| :-- | :-- | :-- | :-- |
| Robust three-field formulation | 📄 | Sigmund, *Acta Mech. Sinica* 2009; Wang, Lazarov & Sigmund, *SMO* 43 (2011) 767–784 | **The most practically important formulation in density-based TO.** Optimise the worst of eroded / intermediate / dilated designs (η > 0.5, 0.5, < 0.5): minimum member size *and* minimum cavity size, results that converge under mesh refinement, and tolerance to over- and under-etching. Costs three FE solves per iteration. It is also what makes an AM-filtered result trustworthy, since one-element-wide members are not printable whatever the overhang filter says. Not strictly a filter — it wraps a Model. |
| Explicit geometric length-scale constraints | 📄 | Guest, *SMO* 2009; Zhou, Lazarov, Wang & Sigmund, *CMAME* 2015 | Imposes minimum length scale as constraints on the filtered fields, avoiding the three-fold cost of the robust formulation. Needs a second constraint slot — see [`updaters/`](../updaters/README.md). |
| Hyperparameter-free minimum length scale | 📄 | [arXiv:2507.16108](https://arxiv.org/abs/2507.16108) (2025) | Recent attempt to remove the tuning that the formulations above require. |

## Candidates — fabrication

The AM overhang, extrusion, pattern-repetition and casting filters are implemented. Everything else in this table is a manufacturing
rule Toporia cannot yet express, and this is where commercial "generative design" tools
actually differentiate.

| Rule | Status | Reference | Why it matters |
| :-- | :-- | :-- | :-- |
| Projection-based self-support | 📄 | Gaynor & Guest, *SMO* 2016 | An alternative overhang treatment to Langelaar's layer-wise filter; worth having both to compare. |
| Enclosed void / powder removal | 📄 | Li et al., *SMO* 2016; Liu et al. 2015 | A virtual temperature field that only heats up inside disconnected voids, penalised to zero. Cheap and elegant. |
| Machining accessibility | 📄 | Langelaar, *CAD* 2019; Lee, Nomura & Dede 2020 | Every solid point reachable by a tool from an allowed set of directions. A generalisation of the AM filter's directional sweep. |
| Residual stress / distortion aware | 📄 | Allaire & Jakabčin 2018; Miki & Yamada, *FEAD* 2021 | An inherent-strain model of the build inside the loop, so the *printed* shape is optimised rather than the designed one. |
| Fibre orientation for composites | 🔗 FRC-TOuNN | Chandrasekhar, Sridhara & Suresh, *CAD* 2022 | Continuous fibre angle alongside density; the angle field itself needs regularising for printable tow paths. |

## References

- T. E. Bruns, D. A. Tortorelli, "Topology optimization of non-linear elastic structures and compliant mechanisms", *CMAME* 190 (2001) 3443–3459.
- O. Sigmund, "Morphology-based black and white filters for topology optimization", *SMO* 33 (2007) 401–424.
- B. S. Lazarov, O. Sigmund, "Filters in topology optimization based on Helmholtz-type differential equations", *IJNME* 86 (2011) 765–781.
- F. Wang, B. S. Lazarov, O. Sigmund, "On projection methods, convergence and robust formulations in topology optimization", *SMO* 43 (2011) 767–784.
- M. Langelaar, "An additive manufacturing filter for topology optimization of print-ready designs", *SMO* 55 (2017) 871–883.
