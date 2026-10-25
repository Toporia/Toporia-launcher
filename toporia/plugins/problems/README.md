# Problems — benchmarks and datasets

A problem is a [`Scenario`](../../framework/problem/scenario.py) — geometry, supports, load cases,
material, volume target — plus the solver settings recommended for it. Two runs that share
a scenario and differ only in their solver are a benchmark, and that comparison is what
Toporia exists to make.

**Status: 12 in Toporia · 6 open datasets or suites · 1 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here, in the problem menu. |
| 🔗 **Open code / data** | A public problem suite or dataset exists. |
| 📄 **Paper only** | Would be written from the paper's geometry. |

## ✅ In Toporia

| Problem | File | Menu name |
| :-- | :-- | :-- |
| ✅ MBB beam | [`mbb_beam.py`](mbb_beam.py) | `MBB Beam` |
| ✅ Cantilever | [`cantilever.py`](cantilever.py) | `Cantilever` |
| ✅ Nonlinear cantilever | [`nonlinear_cantilever.py`](nonlinear_cantilever.py) | `Nonlinear Cantilever` |
| ✅ Cantilever 3D | [`cantilever_3d.py`](cantilever_3d.py) | `Cantilever 3D` |
| ✅ Three-point bending | [`three_point_bending.py`](three_point_bending.py) | `Three-Point Bending` |
| ✅ Standard bar | [`standard_bar.py`](standard_bar.py) | `Standard Bar` |
| ✅ Drone arm | [`drone_arm.py`](drone_arm.py) | `Drone Arm` |
| ✅ Drone arm, camera view | [`drone_arm_camera_view.py`](drone_arm_camera_view.py) | `Drone Arm (Camera View)` |
| ✅ Drone arm, point loads | [`drone_arm_point_loads.py`](drone_arm_point_loads.py) | `Drone Arm (Point Loads)` |
| ✅ Michell cantilever | [`michell_cantilever.py`](michell_cantilever.py) | `Michell Cantilever` |
| ✅ L-bracket | [`l_bracket.py`](l_bracket.py) | `L-bracket` |
| ✅ L-bracket (local stress) | [`l_bracket_stress.py`](l_bracket_stress.py) | `L-bracket (local stress)` |
| ✅ MBB beam, robust | [`mbb_beam_robust.py`](mbb_beam_robust.py) | `MBB Beam (Robust)` |
| ✅ Heat sink | [`heat_sink.py`](heat_sink.py) | `Heat Sink` |

All but the heat sink are compliance problems, which matches what the library can currently
solve (the cantilever 3D is the one 3-D case). Run any of them with `toporia run "<menu name>"`;
| ✅ Vibrating beam | [`vibrating_beam.py`](vibrating_beam.py) | `Vibrating Beam` |

All are compliance problems except the vibrating beam (the cantilever 3D is the one 3-D case). Run any of them with `toporia run "<menu name>"`;
`toporia list` shows the names, `--out DIR` chooses the output folder and
`--set PATH=VALUE` overrides a parameter, e.g. `toporia run "L-bracket" --set m=1`.

The **Michell cantilever** carries a point load to a clamped circular support. Its optimal
layout is known analytically (Michell 1904: orthogonal spirals leaving the circle at 45°),
which makes it the check that a method converges to the right *shape*, not only to a low
number. The analytical optimum is a truss of infinitely many members, so compare layouts
rather than exact values. Run every method on it with **Compare Methods** in the GUI, or
`toporia benchmark --methods q4+oc q4+mma levelset --problems "Michell Cantilever"`.

### Heat sink

A 100 × 100 mm plate that generates heat uniformly over its whole area and loses it only
through a small sink (a half-disc of radius 6 mm held at T = 0) in the middle of the bottom
edge. Distribute 40 % conductor (conductivity 1; the void conducts 1e-3) to minimise the
thermal compliance, which is proportional to the mean temperature. The result is the
tree-like network of conductors of the classic figure. Source: Bendsøe & Sigmund,
*Topology Optimization* (2003), section 1.5; Gersborg-Hansen, Bendsøe & Sigmund, *SMO* 31
(2006) 251-259, [doi](https://doi.org/10.1007/s00158-005-0584-3).

In the GUI pick *Heat Sink* in the problem menu: the physics, the objective and the sink come
with it. On the command line:

```
toporia run "Heat Sink"
```

runs `q4_heat+oc` for 100 iterations on a 50 × 50 mesh (about two seconds); the thermal
compliance falls from 9.02 to 1.36. The scenario's supports are the heat sinks and the load
case's `Fmag` (here 0) is heat entering at point loads; the generation is the physics
parameter `heat_source`. The sensitivities are cross-checked against pyMOTO
(`pymoto_heat`).

### Nonlinear cantilever

The cantilever again (60 × 30, 40 % material, clamped left edge, a point load at mid-height of
the free end, on a solid pad), with a load big enough that the beam bends visibly, designed
with **geometrically non-linear elasticity**: large displacements, Newton–Raphson with load
steps, minimising the compliance at the final load (*end compliance*). It follows the stiffness
design problem of Buhl, Pedersen & Sigmund, *Struct. Multidisc. Optim.* 19 (2000) 93-104
([doi](https://doi.org/10.1007/s001580050089)); the void is handled by an energy interpolation
after Wang, Lazarov, Sigmund & Jensen, *CMAME* 276 (2014) 453-472
([doi](https://doi.org/10.1016/j.cma.2014.03.021)). The open reference code is the 137-line code
of Han et al., *SMO* 63 (2021) ([doi](https://doi.org/10.1007/s00158-020-02816-9)). pyMOTO has
no geometrically non-linear module, so there is no pyMOTO version. How the engine works:
[`physics/`](../physics/README.md).

- **GUI:** pick the problem *Nonlinear Cantilever*; the physics (model) picker already shows
  *2-D Q4, large deformation (Toporia)* and the objective *End compliance (non-linear)*. The
  load steps and Newton settings are the model's parameters. Switching the model back to
  *2-D Q4 plane stress* and the objective to *Compliance* gives the linear design of the same
  problem to compare with.
- **Command line:** `toporia run "Nonlinear Cantilever"`; add `--set max_iter=20` for a quick
  look, `--set method.steps=10` for more load steps, or `--set method=q4+mma --set
  objective.type=compliance` for the linear design of the same problem to compare with.

A load much larger than the preset's makes the first grey designs snap or buckle, which load
control cannot follow; the run then stops with an error naming the load fraction reached.
Lower the load or the move limit.

### L-bracket

A 100 × 100 mm square with the top-right 60 × 60 mm removed (forced empty), so both arms
are 40 mm wide. The top edge of the vertical arm is clamped and a downward point load acts
at mid-height of the free end of the horizontal arm; the volume fraction is 0.4. It is the
standard **stress-concentration benchmark**: the re-entrant corner at (40, 40) is a stress
singularity that a compliance objective happily leaves sharp, and the case exists to show
a stress constraint rounding it off (Duysinx & Bendsøe 1998; Le et al. 2010, which use this
geometry). The preset minimises compliance, which is what `q4+oc` can run:
`toporia run "L-bracket"`. The stress-limited version is the next preset.

### L-bracket (local stress)

The same geometry, solved the way the benchmark asks: minimise volume from a full design under a von Mises limit in
*every* element, by the augmented Lagrangian method (`q4+augmented_lagrangian`, response `local_stress`;
Giraldo-Londoño & Paulino 2021, [PolyStress](https://doi.org/10.1007/s00158-020-02760-8)). The limit (0.5) is below the
stress of the compliance design, so the re-entrant corner has to be relieved. Coarse mesh, 300 iterations:
`toporia run "L-bracket (local stress)"` ends at 24.5 % material and 1.03 × the limit.

### MBB beam, robust

The MBB half-beam again, but every design is evaluated eroded / intermediate / dilated
(Heaviside η = 0.75 / 0.5 / 0.25) and the worst compliance is minimised, with β doubled
from 1 to 64. It shows the robust formulation of Wang, Lazarov & Sigmund (2011) end to end:
`toporia run "MBB Beam (Robust)"`. What it is and how to build it by hand is in the
[schedules README](../schedules/README.md#several-versions-of-one-design-robust-formulations).

### Vibrating beam

A beam 8 × 1 clamped at both ends with a non-structural mass (2, against a solid-beam mass of
8) at its centre; half of the domain may be filled and the **fundamental frequency is
maximised**, after Du & Olhoff (2007). It uses the model *2-D Q4 with vibration* and MMA
(`q4_dynamic+mma`): eigenvalue sensitivities change sign, so OC cannot run it. The payload is
declared as the point load, since the engine hangs its `attached_mass` on the load nodes. The
lowest three eigenvalues are aggregated so a second mode that catches up is raised too, and
the mass interpolation of Pedersen keeps void from producing spurious modes. On the 80 × 10
mesh the fundamental angular frequency rises from 0.0306 to 0.0553 (+81 %) in 100 iterations,
about 12 s. In the GUI pick *Vibrating Beam* in the problem list (the model and objective come
with it); on the command line `toporia run "Vibrating Beam" --out DIR`. Papers:
[Du & Olhoff 2007](https://doi.org/10.1007/s00158-007-0101-y),
[Pedersen 2000](https://doi.org/10.1007/s001580050130).

## 📄 Canonical benchmarks not here yet

Each of these exists specifically to exercise something compliance cannot, so they only
become useful alongside the matching response in [`responses/`](../responses/README.md).

| Problem | Reference | What it tests |
| :-- | :-- | :-- |
| 📄 Force inverter | Sigmund, *Mech. Struct. Mach.* 25 (1997) 493–524; Bendsøe & Sigmund, *Topology Optimization* (2003) | The standard compliant-mechanism benchmark, and where one-node hinges show up. |

**Why the force inverter is not a preset.** Its geometry is easy (a symmetry half-domain,
an input force on one edge, an output on the opposite one), but the objective is to
*maximise the output displacement against an output spring*, with a spring at the input
too. Preset geometry alone would silently optimise compliance, which gives a stiff
structure, the opposite of a mechanism, so it is left out. What is missing:

- an **output-displacement response**: `u_out = lᵀu`, with `l` a unit vector at the output
  node(s) and the objective `-u_out`;
- **input and output springs**: stiffnesses `k_in` and `k_out` added to the diagonal of
  the stiffness matrix at those degrees of freedom (the scenario has no spring type today,
  only fixed supports and point loads);
- the **gradient**: one adjoint solve per iteration with `l` as the load, through the
  physics `adjoint()` and `mutual_energy()` (see
  [`framework/parts/physics.py`](../../framework/parts/physics.py)), the way the stress
  response does it; the response is not self-adjoint, so its sensitivities are signed and
  the usual OC update needs a negative-sensitivity guard (MMA is the safe pairing).

Further standard cases, each tied to a response Toporia does not have yet: half-wheel and
bridge (compliance, alternative load paths), column (buckling), heat sink (thermal),
double pipe and bend (fluid pressure drop), and the photonic mode converter and
beam-splitter from the ceviche challenges.

## 🔗 Open datasets and benchmark suites

| Dataset / suite | Where | Contents |
| :-- | :-- | :-- |
| 🔗 SELTO | [Zenodo](https://zenodo.org/records/7781392) · [arXiv:2209.05098](https://arxiv.org/abs/2209.05098) | Four 3-D datasets (disc and sphere, simple and complex), ~10,000 problem/solution pairs with ground-truth SIMP densities generated with OptiStruct. The reference dataset for learned TO. |
| 🔗 dl4to | [GitHub](https://github.com/dl4to/dl4to) | The PyTorch library that ships SELTO, with a ready benchmark harness. |
| 🔗 ceviche-challenges | [GitHub](https://github.com/google/ceviche-challenges) | Google's photonic inverse-design suite: fixed problems, fixed metric, any optimiser, all behind one API. **The structure worth copying for a mechanics suite.** |
| 🔗 Topology optimization dataset | [Zenodo](https://zenodo.org/records/8191138) | General-purpose problem/solution pairs. |
| 🔗 DeepJEB | [arXiv:2406.09047](https://arxiv.org/abs/2406.09047) | Synthetic 3-D jet-engine bracket dataset — a realistic industrial geometry family. |
| 🔗 GE jet engine bracket challenge | GrabCAD | The original industrial TO challenge geometry, widely used as an informal benchmark. |

## The gap worth filling

There is **no accepted cross-method benchmark for mechanics.** Papers report their own
problem, their own mesh and their own filter radius, so SIMP-against-BESO-against-level-set
comparisons in the literature are rarely like-for-like. A suite that fixes the scenario,
the mesh and the volume fraction, and varies only the method, the filter and the updater,
is a genuine contribution — and it is already most of the way there in
[`engine/compare_two.py`](../../engine/modes/compare.py),
[`engine/sweep.py`](../../engine/modes/sweep.py) and
[`engine/sweep_2d.py`](../../engine/modes/sweep.py).

## References

- A. G. M. Michell, "The limits of economy of material in frame-structures", *Phil. Mag.* 8 (1904) 589–597.
- S. Erzmann, C. Dittmer, et al., "SELTO: sample-efficient learned topology optimization", [arXiv:2209.05098](https://arxiv.org/abs/2209.05098).
- O. Sigmund, "On the usefulness of non-gradient approaches in topology optimization", *SMO* 43 (2011) 589–596 — on why benchmark resolution and function-evaluation counts must be reported together.
