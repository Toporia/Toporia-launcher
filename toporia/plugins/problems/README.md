# Problems — benchmarks and datasets

A problem is a [`Scenario`](../../framework/problem/scenario.py) — geometry, supports, load cases,
material, volume target — plus the solver settings recommended for it. Two runs that share
a scenario and differ only in their solver are a benchmark, and that comparison is what
Toporia exists to make.

**Status: 7 in Toporia · 6 open datasets or suites · 3 paper only**

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
| ✅ Three-point bending | [`three_point_bending.py`](three_point_bending.py) | `Three-Point Bending` |
| ✅ Standard bar | [`standard_bar.py`](standard_bar.py) | `Standard Bar` |
| ✅ Drone arm | [`drone_arm.py`](drone_arm.py) | `Drone Arm` |
| ✅ Drone arm, camera view | [`drone_arm_camera_view.py`](drone_arm_camera_view.py) | `Drone Arm (Camera View)` |
| ✅ Drone arm, point loads | [`drone_arm_point_loads.py`](drone_arm_point_loads.py) | `Drone Arm (Point Loads)` |

All seven are 2-D compliance problems, which matches what the library can currently solve.

## 📄 Canonical benchmarks not here yet

Each of these exists specifically to exercise something compliance cannot, so they only
become useful alongside the matching response in [`responses/`](../responses/README.md).

| Problem | Reference | What it tests |
| :-- | :-- | :-- |
| 📄 **Michell cantilever** | Michell, *Phil. Mag.* 1904 | **The only problem in the field with a known exact optimum.** Everything else is compared against other codes; this one can be compared against the truth. The single most valuable addition to this folder. |
| 📄 L-bracket | Duysinx & Bendsøe, *IJNME* 1998 | The standard stress-concentration benchmark: the re-entrant corner that a compliance objective happily leaves sharp. |
| 📄 Force inverter | Sigmund, *Mech. Struct. Mach.* 1997 | The standard compliant-mechanism benchmark, and where one-node hinges show up. |

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
