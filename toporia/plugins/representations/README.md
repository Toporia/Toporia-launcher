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

**Status: 2 in Toporia · 2 with open code · 3 paper only**

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

**Using MMC.** Every variable is scaled to [0, 1] across its whole range, so the updater's
move limit moves a bar a long way. Use `method.move` of about 0.02. With the usual 0.2,
bars jump off the load and back, and the objective spikes by orders of magnitude before
it recovers. The Pipeline box and the console both give this advice. On the MBB beam
(m = 0.5, 60 iterations of MMA), the bars reach a compliance of about 240–280, against 249
for element densities.

Differences from the reference code MMC188:

- the union of the bars is a smooth product, not a maximum;
- the Heaviside is a tanh about one element wide, taken at element centres;
- a bar's thickness is constant along its length.

Each change simplifies the gradient; `toporia check representation:mmc` checks that
gradient against finite differences.

## Candidates

| Representation | Code | Reference | What it adds |
| :-- | :-- | :-- | :-- |
| 📄 Moving morphable voids (MMV) | — | Zhang et al., *CMAME* 2017 | Holes instead of bars, carved out of a solid domain: the dual of MMC. |
| 🔗 Variable-thickness MMC | MMC188 | Zhang, Yuan, Zhang & Guo, *SMO* 2016 | Thickness varying linearly along each bar (two more variables per bar), as the reference code does. |
| 🔗 Geometry projection / feature mapping | [GPTO](https://github.com/jnorato/GPTO), [GGP](https://github.com/topggp/GGP-Matlab) | Norato, Bell & Tortorelli, *IJNME* 2015; Wein, Dunning & Norato, *SMO* 2020 (review) | Bars with round ends, projected through a signed distance and a size variable that can switch each bar off. |
| 📄 Neural-network reparameterisation | — | Hoyer, Sohl-Dickstein & Greydanus, arXiv 2019; Chandrasekhar & Suresh, *SMO* 2021 | Network weights as the variables, its output as the density field: an implicit regulariser. Needs an autodiff library, declared through `dependencies`. |
| 📄 B-spline fields | — | Qian, *CMAME* 2013 | A smooth field from a few coefficients: built-in length-scale control and few variables. |

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
- J. A. Norato, B. K. Bell, D. A. Tortorelli, "A geometry projection method for continuum-based topology optimization with discrete elements", *IJNME* (2015).
