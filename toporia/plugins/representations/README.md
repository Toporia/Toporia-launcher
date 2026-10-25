# Design representations — what the design variables are

Every density method needs a density per element in the end. What the optimiser moves
doesn't have to be that density. It can be the densities themselves, or the position,
length, thickness and angle of a few dozen bars, or the coefficients of a smooth field.
The representation turns the variables `z` into the element density field and carries
the gradient back:

```
z ──density(z)──> element field ──filters──> ρ ──physics──> responses
dz <──backward──── d(field) <──filter adjoint── dρ <──────── gradients
```

It is a part of its own — see
[`framework/parts/representation.py`](../../framework/parts/representation.py) — chosen in
the solver like the filters and the material law,
`solver.representation = {"type": "mmc", "n_x": 4, "n_y": 2}`. It also sets the start
design and the bounds of every variable. In the GUI it is the **Design representation**
panel, and the Pipeline box shows it as the first stage ("Design").

Any model assembled from parts ([`models/assembled.py`](../models/assembled.py), such as
`q4`) takes it. Models that keep their own variables (pyMOTO's, the level set) ignore it,
and the panel is hidden for them.

**Which updaters work with it.** Updaters that work on any vector (MMA, GCMMA, SLSQP) work
with every representation. Updaters whose rule moves each element's density on its own
(optimality criteria, BESO, SiMPL) declare `needs_element_densities`. Pairing one of them
with another representation is refused before the run, with the reason. The GUI's Pipeline
box shows the same reason, and Compare Methods skips the pairing.

**Status: 4 plugins in Toporia (MMC includes two thickness options) · 1 with open code · 1 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here, registered, passes `toporia check representation:<name>`. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Representation | File | Name | Variables | Reference |
| :-- | :-- | :-- | :-- | :-- |
| ✅ Element densities | [`element_density.py`](element_density.py) | `element_density` | one density per element; starts uniform at the volume fraction or full (`start`) | Bendsøe, *Struct. Optim.* 1989 |
| ✅ Moving morphable components | [`mmc.py`](mmc.py) | `mmc` | 5 per bar (centre, half-length, half-thickness, angle); starts as crossing bars in an `n_x × n_y` grid. 2-D only; 3-D components are a candidate | Guo, Zhang & Zhong, *J. Appl. Mech.* 2014 |
| ✅ Variable-thickness MMC | [`mmc.py`](mmc.py) with `thickness = variable` | `mmc` | the same bars with the half-thickness at both ends and the middle (7 per bar), joined by a parabola, as in MMC188. 2-D only | Zhang, Yuan, Zhang & Guo, *SMO* 2016 |
| ✅ Moving morphable voids | [`mmv.py`](mmv.py) | `mmv` | 5 per superelliptical hole; solid outside their union. Restricted 2-D variant | Zhang et al., *CMAME* 2017 |
| ✅ B-spline field | [`bspline.py`](bspline.py) | `bspline` | the coefficients of a tensor-product B-spline (degree 2 or 3) on a coarse control grid; the density is the spline at the element centres. 2-D and 3-D | Qian, *CMAME* 2013 |

**Using MMC.** Every variable is scaled to [0, 1] across its whole range, so the updater's
move limit moves a bar a long way. Use `method.move` of about 0.02. With the usual 0.2,
bars jump off the load and back, and the objective spikes by orders of magnitude before
it recovers. The Pipeline box and the console both give this advice. On the MBB beam
(m = 0.5, 60 iterations of MMA), the bars reach a compliance of about 240–280, against 249
for element densities.

Differences from the reference code MMC188:

- the union of the bars is a smooth product, not a maximum;
- the Heaviside is a tanh about one element wide, taken at element centres;
- by default a bar's thickness is constant along its length; `thickness = variable` gives the reference's varying thickness (below).

Each change simplifies the gradient; `toporia check representation:mmc` checks that
gradient against finite differences.

### Variable-thickness MMC

**What it does.** The same bars as above, but each one can taper or bulge. Its half-thickness
is given at the left end, the middle and the right end (`t1`, `t2`, `t3`), and the thickness in
between is the parabola through them, as in MMC188. A bar has 7 variables instead of 5. With
`t1 = t2 = t3` it is the constant bar, and the default `thickness = constant` is unchanged
to the bit.

**When to use it.** When tapered members suit the load path (cantilever arms, fans of bars
at a support), or when the constant-thickness bars cannot reach a good compliance. It has
more freedom, so it needs more iterations: on the MBB beam (m = 0.5, MMA, move 0.02)
60 iterations give about 251 and 150 give about 236, against about 234 for constant bars at 60
(element densities: about 218).

**Paper.** W. Zhang, J. Yuan, J. Zhang, X. Guo, "A new topology optimization approach based on
Moving Morphable Components (MMC) and the ersatz material model", *Struct. Multidisc. Optim.*
53 (2016) 1243-1260.

**How to use it.** In a config, `solver.representation = {"type": "mmc", "thickness": "variable"}`.
In the GUI, pick *Moving morphable components* in the Design representation panel and set
*Thickness along a bar* to *Varying along the bar*. On the command line:

```
toporia run "MBB Beam" --set method=q4+mma --set representation.type=mmc \
    --set representation.thickness=variable --set method.move=0.02 --set max_iter=150
```

Keep `method.move` at about 0.02, as for constant bars. `toporia check representation:mmc`
checks the constant form; the varying form's gradient is checked against finite differences
in `tests/plugins/test_representation.py`.

### B-spline fields

**What it does.** The variables are the coefficients of a tensor-product B-spline on a coarse
control grid (`n_x` × `n_y`, and `n_z` in 3-D). The element density is the spline evaluated at
the element centres. That map is linear and fixed, so `backward` is its transpose. The basis
functions are non-negative and sum to one, so coefficients in [0, 1] give densities in
[0, 1] with no clipping: a field of ones is all ones, and the start design (every
coefficient equal to the volume fraction) is that density everywhere.

**When to use it.** For a smooth density field with a built-in length scale and far fewer
variables than elements: refine the mesh and the problem does not grow. The control grid sets
the finest feature, so choose it about as fine as the thinnest member you want. The field is
not made black and white by the representation, so use the usual material law (and a
projection filter) for that. It works in 2-D and 3-D, and with MMA, GCMMA and SLSQP; element
updaters (OC, BESO, SiMPL) are refused.

On the MBB beam (MMA, tol 0, 150 iterations) a 36 × 12 grid reaches a compliance of about
246 with degree 2 and 264 with degree 3 (element densities: about 218 at 60 iterations); a
24 × 8 grid gives about 297 and stops early on the design-change tolerance.

**Paper.** X. Qian, "Topology optimization in B-spline space", *Comput. Methods Appl. Mech.
Engrg.* 265 (2013) 15-35.

**How to use it.** In a config, `solver.representation = {"type": "bspline", "n_x": 36, "n_y": 12, "degree": 2}`.
In the GUI, pick *B-spline field* in the Design representation panel. On the command line:

```
toporia run "MBB Beam" --set method=q4+mma --set representation.type=bspline \
    --set representation.n_x=36 --set representation.n_y=12 --set representation.degree=2 \
    --set tol=0 --set max_iter=150
```

`toporia check representation:bspline` passes (finite-difference `backward`, a short `q4+mma` run).
### Moving morphable voids

`mmv` starts with one hole in each cell of an `n_x` × `n_y` layout. Each has
five normalised variables: centre x/y, two half-axes and angle. The same
sixth-order superellipse as MMC describes the hole. Material density is
`product(1 - H(phi_i))`, with MMC's smoothed tanh boundary; the adjoint uses
prefix/suffix products so fully void overlaps never cause division by zero.
`start_size` sets the initial half-axes relative to the layout cell. Holes can
move, resize, rotate and merge. Their number is fixed; new holes cannot nucleate.
The inherited `outlines()` export returns the individual hole boundaries.

This is an own restricted 2-D implementation of the MMV idea, not a port of
the cited 3-D implementation. It retains the full ersatz FE mesh and does not
implement the paper's B-spline surfaces, FE DOF removal or CAD reconstruction.
Choose enough initial holes for the desired topology, and resolve boundaries
with the mesh before reducing `edge_width`. Hole axes have mesh-scale lower
bounds, so this family cannot exactly remove a hole by shrinking it to zero.
Use MMA with `method.move` about 0.02; element-wise updaters such as OC are refused.

```
toporia run "MBB Beam" --set method=q4+mma --set representation.type=mmv \
    --set method.move=0.02 --set m=0.5 --set tol=0 --set max_iter=60
```

`toporia check representation:mmv` checks the adjoint and a short optimisation.
Additional tests cover rotated/overlapping holes, saturation and feasible optimisation.
The reference is W. Zhang et al., *CMAME* 322 (2017) 590–614,
[DOI 10.1016/j.cma.2017.05.002](https://doi.org/10.1016/j.cma.2017.05.002);
the [authors' manuscript](https://arxiv.org/abs/1704.06060), section 2,
describes MMV as the geometric dual of MMC.

## Candidates

| Representation | Code | Reference | What it adds |
| :-- | :-- | :-- | :-- |
| 🔗 Geometry projection / feature mapping | [GPTO](https://github.com/jnorato/GPTO), [GGP](https://github.com/topggp/GGP-Matlab) | Norato, Bell & Tortorelli, *IJNME* 2015; Wein, Dunning & Norato, *SMO* 2020 (review) | Bars with round ends, projected through a signed distance and a size variable that can switch each bar off. |
| 📄 Neural-network reparameterisation | — | Hoyer, Sohl-Dickstein & Greydanus, arXiv 2019; Chandrasekhar & Suresh, *SMO* 2021 | Network weights as the variables, its output as the density field: an implicit regulariser. Needs an autodiff library, declared through `dependencies`. |

## Writing one

Subclass `Representation` and give it `name`, `label` and `params` (the constructor takes
each one as a keyword). Then implement:

- `setup(problem)`;
- `initial()` and `bounds()`;
- `density(z)`, which returns a `(nely, nelx)` field in [0, 1];
- `backward(z, sensitivity)`, the chain rule back to `z`.

Set `element_wise = True` only when the variables *are* the element densities. Then run
`toporia check representation:<name>`. It checks the field's shape and range, that the
start design lies within the bounds, `backward` against finite differences, and a short
run with `q4+mma`. A worked example (a mirror-symmetric design) is in
[docs/writing-plugins.md](../../../docs/writing-plugins.md).

## References

- M. P. Bendsøe, "Optimal shape design as a material distribution problem", *Structural Optimization* 1 (1989) 193–202.
- X. Guo, W. Zhang, W. Zhong, "Doing topology optimization explicitly and geometrically — a new moving morphable components based framework", *Journal of Applied Mechanics* 81 (2014) 081009.
- W. Zhang, J. Yuan, J. Zhang, X. Guo, "A new topology optimization approach based on Moving Morphable Components (MMC) and the ersatz material model", *SMO* 53 (2016).
- X. Qian, "Topology optimization in B-spline space", *Comput. Methods Appl. Mech. Engrg.* 265 (2013) 15-35.
- J. A. Norato, B. K. Bell, D. A. Tortorelli, "A geometry projection method for continuum-based topology optimization with discrete elements", *IJNME* (2015).
