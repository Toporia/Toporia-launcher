# The Toporia library: every code in it, where it comes from, and what to add next

This page lists **every part you can pick in Toporia today**, what it is, where it comes
from and how it got here. The second half is the list of what is still to be added.

- Each kind of part has its own folder and README with the details and the formulas.
- The [survey](SURVEY.md) lists every open topology-optimisation code that was found, with
  links and licences.
- The [to-do list](TODO.md) is the working plan behind the list below.

Every part on this page:
- appears in the desktop app;
- has a **?** button in the app that shows the same reference as here;
- passes `toporia check <kind>:<name>`.

A test (`tests/apps/test_gui.py`) fails if a part ever stops being reachable from the app.

## How a part came in

| Mark | Meaning |
| :-- | :-- |
| **Port** | Translated into Python from a published code (usually MATLAB). The original is named. |
| **Paper** | Written here from the paper. No code was copied. |
| **Wraps** | Calls an outside Python package. That package is installed separately. Parts whose package is missing are greyed out in the app, with the install command. |
| **Own** | Toporia's own idea or standard practice. |

## In the library today: 57 parts and 11 benchmark problems

### Design representations: what the design variables are ([folder](representations/README.md))

| In the app | Name | File | Came in | From |
| :-- | :-- | :-- | :-- | :-- |
| Element densities | `element_density` | [element_density.py](representations/element_density.py) | Own | Bendsøe 1989; Sigmund's 99-line code · papers [1](https://doi.org/10.1007/BF01650949) [2](https://doi.org/10.1007/s001580050176) |
| Moving morphable components (constant or variable thickness) | `mmc` | [mmc.py](representations/mmc.py) | Paper | Guo, Zhang & Zhong 2014; variable thickness as in MMC188 (Zhang et al., *SMO* 2016) · papers [1](https://doi.org/10.1115/1.4027609) [2](https://doi.org/10.1007/s00158-015-1372-3) |
| B-spline field | `bspline` | [bspline.py](representations/bspline.py) | Paper | Qian, *CMAME* 2013 · [paper](https://doi.org/10.1016/j.cma.2013.06.001) |

### Filters: design to physical density, and fabrication rules ([folder](filters/README.md))

| In the app | Name | File | Came in | From |
| :-- | :-- | :-- | :-- | :-- |
| Density filter | `density` | [density.py](filters/density.py) | Port | top88 (Andreassen et al. 2011); Bruns & Tortorelli 2001; Bourdin 2001 · papers [1](https://doi.org/10.1016/S0045-7825%2800%2900278-4) [2](https://doi.org/10.1002/nme.116) [3](https://doi.org/10.1007/s00158-010-0594-7) |
| PDE (Helmholtz) filter | `pde` | [pde.py](filters/pde.py) | Port | the PDE variant of top88 (top82.m); Lazarov & Sigmund 2011 · papers [1](https://doi.org/10.1002/nme.3072) [2](https://doi.org/10.1007/s00158-010-0594-7) |
| Sensitivity filter | `sensitivity` | [sensitivity.py](filters/sensitivity.py) | Port | Sigmund 1997, as in the 99-line code and top88 · papers [1](https://doi.org/10.1080/08905459708945415) [2](https://doi.org/10.1007/s001580050176) [3](https://doi.org/10.1007/s00158-010-0594-7) |
| Heaviside projection (fixed or volume-preserving threshold) | `heaviside` | [heaviside.py](filters/heaviside.py) | Paper | Guest et al. 2004; Wang, Lazarov & Sigmund 2011; volume-preserving as in top99neo (Ferrari & Sigmund 2020) · papers [1](https://doi.org/10.1002/nme.1064) [2](https://doi.org/10.1007/s00158-010-0602-y) [3](https://doi.org/10.1007/s00158-020-02629-w) |
| Morphology filter (erode / dilate / open / close) | `morphology` | [morphology.py](filters/morphology.py) | Paper | Sigmund, *SMO* 2007 · [paper](https://doi.org/10.1007/s00158-006-0087-x) |
| AM overhang filter | `am` | [am.py](filters/am.py) | Port | Langelaar's AMfilter.m (*SMO* 2017) · papers [1](https://doi.org/10.1007/s00158-016-1522-2) [2](https://doi.org/10.1016/j.addma.2016.06.010) |
| Routing radius filter | `routing` | [routing.py](filters/routing.py) | Own | inspired by Sigmund 2007 · [paper](https://doi.org/10.1007/s00158-006-0087-x) |
| Symmetry filter | `symmetry` | [symmetry.py](filters/symmetry.py) | Own | standard practice · [paper](https://doi.org/10.1007/978-3-662-05086-6) |
| Extrusion (constant cross-section) | `extrusion` | [extrusion.py](filters/extrusion.py) | Paper | Ishii & Aomura 2004 · [paper](https://doi.org/10.1299/jsmea.47.198) |
| Pattern repetition | `pattern` | [pattern.py](filters/pattern.py) | Paper | Bendsøe & Sigmund 2003; Almeida, Paulino & Silva 2009 · papers [1](https://doi.org/10.1007/978-3-662-05086-6) [2](https://doi.org/10.1007/s00158-008-0332-6) |
| Casting (no undercuts) | `casting` | [casting.py](filters/casting.py) | Paper | Gersborg & Andreasen, *SMO* 2011 · [paper](https://doi.org/10.1007/s00158-011-0632-0) |

### Material laws: density to stiffness ([folder](interpolations/README.md))

| In the app | Name | File | Came in | From |
| :-- | :-- | :-- | :-- | :-- |
| SIMP (power law) | `simp` | [simp.py](interpolations/simp.py) | Paper | Bendsøe 1989 · [paper](https://doi.org/10.1007/BF01650949) |
| RAMP (rational) | `ramp` | [ramp.py](interpolations/ramp.py) | Paper | Stolpe & Svanberg 2001 · [paper](https://doi.org/10.1007/s001580100129) |
| Ordered SIMP (multi-material) | `ordered_simp` | [ordered_simp.py](interpolations/ordered_simp.py) | Paper | Zuo & Saitou, *SMO* 2017 · [paper](https://doi.org/10.1007/s00158-016-1513-3) |

### Physics models: what computes displacements and gradients ([folder](models/README.md), elements in [physics/](physics/README.md))

| In the app | Name | File | Came in | From |
| :-- | :-- | :-- | :-- | :-- |
| 2-D Q4 plane stress (Toporia) | `q4` | [q4.py](models/q4.py), [q4_plane_stress.py](physics/q4_plane_stress.py) | Port | the physics half of top88 · [paper](https://doi.org/10.1007/s00158-010-0594-7) |
| 2-D Q4, large deformation (Toporia) | `q4_nonlinear` | [q4_nonlinear.py](models/q4_nonlinear.py), [q4_nonlinear.py](physics/q4_nonlinear.py) | Paper | Buhl, Pedersen & Sigmund, *SMO* 2000; energy interpolation after Wang, Lazarov, Sigmund & Jensen, *CMAME* 2014; open reference: Han et al. 2021 · papers [1](https://doi.org/10.1007/s001580050089) [2](https://doi.org/10.1016/j.cma.2014.03.021) [3](https://doi.org/10.1007/s00158-020-02816-9) |
| 3-D H8 bricks (Toporia) | `h8` | [h8.py](models/h8.py), [h8_solid.py](physics/h8_solid.py) | Port | top3d (Liu & Tovar, *SMO* 2014) · [paper](https://doi.org/10.1007/s00158-014-1107-x) |
| Linear elasticity, pyMOTO network | `pymoto_elastic` | [pymoto_elastic.py](models/pymoto_elastic.py) | Wraps | [pyMOTO](https://github.com/aatmdelissen/pyMOTO) (MIT), `pip install pymoto` |
| 2-D Q4 heat conduction (Toporia) | `q4_heat` | [q4_heat.py](models/q4_heat.py), [q4_heat.py](physics/q4_heat.py) | Paper | Bendsøe & Sigmund 2003, section 1.5; Gersborg-Hansen et al., *SMO* 2006 · [paper](https://doi.org/10.1007/s00158-005-0584-3) |
| 3-D H8 heat conduction (Toporia) | `h8_heat` | [h8_heat.py](models/h8_heat.py), [h8_heat.py](physics/h8_heat.py) | Paper | the 3-D brick of the same heat problem · [paper](https://doi.org/10.1007/s00158-005-0584-3) |
| Heat conduction, pyMOTO network | `pymoto_heat` | [pymoto_heat.py](models/pymoto_heat.py) | Wraps | [pyMOTO](https://github.com/aatmdelissen/pyMOTO)'s `AssemblePoisson` (MIT), `pip install pymoto`; the cross-check of `q4_heat` |
| 2-D Q4 with vibration (Toporia) | `q4_dynamic` | [q4_dynamic.py](models/q4_dynamic.py), [q4_dynamic.py](physics/q4_dynamic.py) | Paper | Pedersen, *SMO* 2000; Du & Olhoff, *SMO* 2007 · papers [1](https://doi.org/10.1007/s001580050130) [2](https://doi.org/10.1007/s00158-007-0101-y) |
| Vibration, pyMOTO network | `pymoto_dynamic` | [pymoto_dynamic.py](models/pymoto_dynamic.py) | Wraps | [pyMOTO](https://github.com/aatmdelissen/pyMOTO) `AssembleMass` and `EigenSolve`, `pip install pymoto` |

### Objectives and constraints ([folder](responses/README.md))

| In the app | Name | File | Came in | From |
| :-- | :-- | :-- | :-- | :-- |
| Compliance | `compliance` | [compliance.py](responses/compliance.py) | Own | the classic objective (Bendsøe & Sigmund 2003) · [paper](https://doi.org/10.1007/978-3-662-05086-6) |
| Material volume | `volume` | [volume.py](responses/volume.py) | Own | as in Le et al. 2010 and pyMOTO's stress example · [paper](https://doi.org/10.1007/s00158-009-0440-y) |
| Local von Mises stress (augmented Lagrangian) | `local_stress` | [local_stress.py](responses/local_stress.py) | Paper | Giraldo-Londoño & Paulino, *SMO* 2021 (PolyStress); Senhora et al., *SMO* 2020 · papers [1](https://doi.org/10.1007/s00158-020-02760-8) [2](https://doi.org/10.1007/s00158-020-02573-9) |
| End compliance (non-linear) | `end_compliance` | [end_compliance.py](responses/end_compliance.py) | Paper | Buhl, Pedersen & Sigmund, *SMO* 2000 · [paper](https://doi.org/10.1007/s001580050089) |
| Peak von Mises stress | `stress` | [stress.py](responses/stress.py) | Paper | Le, Norato, Bruns, Ha & Tortorelli, *SMO* 2010 · [paper](https://doi.org/10.1007/s00158-009-0440-y) |
| Thermal compliance | `thermal_compliance` | [thermal_compliance.py](responses/thermal_compliance.py) | Paper | Bendsøe & Sigmund 2003, section 1.5; Gersborg-Hansen et al., *SMO* 2006 · [paper](https://doi.org/10.1007/s00158-005-0584-3) |
| Fundamental frequency (maximise) | `eigenfrequency` | [eigenfrequency.py](responses/eigenfrequency.py) | Paper | Díaz & Kikuchi, *IJNME* 1992; Du & Olhoff, *SMO* 2007 · papers [1](https://doi.org/10.1002/nme.1620350707) [2](https://doi.org/10.1007/s00158-007-0101-y) |
| Fundamental frequency (at least) | `eigenfrequency_limit` | [eigenfrequency.py](responses/eigenfrequency.py) | Paper | the same, as a constraint |
| Dynamic compliance (harmonic load) | `dynamic_compliance` | [dynamic_compliance.py](responses/dynamic_compliance.py) | Paper | Ma, Kikuchi & Hagiwara, *Comput. Mech.* 1993 (no link); PolyDyna · [paper](https://doi.org/10.1007/s00158-021-02859-6) |

### Optimisers: how the design moves ([folder](updaters/README.md))

| In the app | Name | File | Came in | From |
| :-- | :-- | :-- | :-- | :-- |
| Optimality criteria | `oc` | [oc.py](updaters/oc.py) | Port | the 99-line code and top88 · papers [1](https://doi.org/10.1007/s001580050176) [2](https://doi.org/10.1007/s00158-010-0594-7) |
| Optimality criteria, several constraints | `oc_multi` | [oc_multi.py](updaters/oc_multi.py) | Own | after Zhou & Rozvany 1991 · [paper](https://doi.org/10.1016/0045-7825%2891%2990046-9) |
| Method of moving asymptotes | `mma` | [mma.py](updaters/mma.py) | Port | Svanberg 1987, one-constraint form of top88's MMA variant · papers [1](https://doi.org/10.1002/nme.1620240207) [2](https://doi.org/10.1007/s00158-010-0594-7) |
| CONLIN (convex linearisation) | `conlin` | [conlin.py](updaters/conlin.py) | Paper | Fleury & Braibant 1986; Fleury 1989 · papers [1](https://doi.org/10.1002/nme.1620230307) [2](https://doi.org/10.1007/BF01743804) |
| Mirror descent (SiMPL) | `simpl` | [simpl.py](updaters/simpl.py) | Paper | Keith, Kim, Lazarov & Surowiec, *SMO* 2025 · [paper](https://doi.org/10.1007/s00158-025-04008-9) |
| BESO (soft kill) | `beso` | [beso.py](updaters/beso.py) | Paper | Huang & Xie 2007, 2010 · papers [1](https://doi.org/10.1016/j.finel.2007.06.006) [2](https://doi.org/10.1002/9780470689486) |
| BESO (hard kill) | `beso_hard` | [beso_hard.py](updaters/beso_hard.py) | Paper | Huang & Xie 2010 · papers [1](https://doi.org/10.1002/9780470689486) [2](https://doi.org/10.1007/s001580050170) |
| TOBS (integer LP) | `tobs` | [tobs.py](updaters/tobs.py) | Paper | Sivapuram & Picelli 2018; the 101-line code of Picelli et al. 2021; solved with HiGHS (SciPy) · papers [1](https://doi.org/10.1016/j.finel.2017.10.006) [2](https://doi.org/10.1007/s00158-020-02719-9) |
| Augmented Lagrangian (local constraints) | `augmented_lagrangian` | [augmented_lagrangian.py](updaters/augmented_lagrangian.py) | Paper | PolyStress outer loop (Giraldo-Londoño & Paulino 2021) with MMA inner steps · papers [1](https://doi.org/10.1007/s00158-020-02760-8) [2](https://doi.org/10.1007/s00158-010-0594-7) |
| Adam (augmented Lagrangian) | `adam` | [adam.py](updaters/adam.py) | Paper | Kingma & Ba 2015; the volume penalty of TOuNN (Chandrasekhar & Suresh 2021) · papers [1](https://arxiv.org/abs/1412.6980) [2](https://doi.org/10.1007/s00158-020-02748-4) |
| Proportional topology optimisation | `pto` | [pto.py](updaters/pto.py) | Paper | Biyikli & To, *PLoS ONE* 2015 · [paper](https://doi.org/10.1371/journal.pone.0145041) |
| MMA (pyMOTO), GCMMA (pyMOTO) | `pymoto_mma`, `pymoto_gcmma` | [pymoto_optimizers.py](updaters/pymoto_optimizers.py) | Wraps | [pyMOTO](https://github.com/aatmdelissen/pyMOTO) (MIT) · papers [1](https://doi.org/10.1002/nme.1620240207) [2](https://doi.org/10.1137/S1052623499362822) |
| MMA (mmapy), GCMMA (mmapy) | `mmapy_mma`, `mmapy_gcmma` | [mmapy_optimizers.py](updaters/mmapy_optimizers.py) | Wraps | [mmapy](https://github.com/arjendeetman/GCMMA-MMA-Python), Svanberg's reference code in Python (**GPL-3**, optional), `pip install mmapy` · papers [1](https://doi.org/10.1002/nme.1620240207) [2](https://doi.org/10.1137/S1052623499362822) |
| SLSQP (SciPy) | `scipy_slsqp` | [scipy_slsqp.py](updaters/scipy_slsqp.py) | Wraps | SciPy (BSD), Kraft 1988 |
| trust-constr (SciPy) | `scipy_trust_constr` | [scipy_minimize.py](updaters/scipy_minimize.py) | Wraps | SciPy (BSD) · [paper](https://doi.org/10.1137/1.9780898719857) |
| MMA, CCSAQ, SLSQP, augmented Lagrangian + L-BFGS (NLopt) | `nlopt_mma`, `nlopt_ccsaq`, `nlopt_slsqp`, `nlopt_auglag` | [nlopt_optimizers.py](updaters/nlopt_optimizers.py) | Wraps | [NLopt](https://nlopt.readthedocs.io) (LGPL/MIT), `pip install nlopt` · papers [1](https://doi.org/10.1002/nme.1620240207) [2](https://doi.org/10.1137/S1052623499362822) [3](https://doi.org/10.1137/0728030) [4](https://doi.org/10.1080/10556780701577730) |
| Null-space optimiser | `nullspace` | [nullspace.py](updaters/nullspace.py) | Wraps | [null-space optimizer](https://gitlab.com/florian.feppon/null-space-optimizer) of Feppon, Allaire & Dapogny 2020 (**GPL-3**, optional), `pip install nullspace_optimizer` · [paper](https://doi.org/10.1051/cocv/2020015) |

### Whole methods: their own loop ([folder](methods/README.md))

| In the app | Name | File | Came in | From |
| :-- | :-- | :-- | :-- | :-- |
| RBF level set | `levelset` | [levelset_rbf.py](methods/levelset_rbf.py) | Port | TOPRBF.m (Luo et al.); Wang & Wang, *CMAME* 2006 · papers [1](https://doi.org/10.1002/nme.1536) [2](https://doi.org/10.1007/s00158-018-1904-8) |

Every model can also be paired with every optimiser as a method called `<model>+<optimiser>`,
for example `q4+nlopt_mma`. Those pairings are built on demand, so they are not listed here.

### Continuation: parameters that change during a run ([folder](schedules/README.md))

| In the app | Name | File | Came in | From |
| :-- | :-- | :-- | :-- | :-- |
| Equal steps | `steps` | [steps.py](schedules/steps.py) | Own | the classic SIMP continuation (Sigmund & Petersson 1998) · [paper](https://doi.org/10.1007/BF01214002) |
| Multiply by a factor | `geometric` | [geometric.py](schedules/geometric.py) | Own | the usual β continuation (Guest et al. 2004; Wang et al. 2011) · papers [1](https://doi.org/10.1002/nme.1064) [2](https://doi.org/10.1007/s00158-010-0602-y) |
| Linear ramp | `linear` | [linear.py](schedules/linear.py) | Own | — |
| When the design settles | `settled` | [settled.py](schedules/settled.py) | Own | common practice in the projection literature (Wang et al. 2011) · [paper](https://doi.org/10.1007/s00158-010-0602-y) |

The robust formulation (one design evaluated in several versions) is a solver setting rather
than a schedule. See the [schedules README](schedules/README.md#several-versions-of-one-design-robust-formulations)
and the preset *MBB Beam (Robust)*.

### Post-processing: what is made of the finished design ([folder](postprocessors/README.md))

| In the app | Name | File | Came in | From |
| :-- | :-- | :-- | :-- | :-- |
| Threshold to black and white | `threshold` | [threshold.py](postprocessors/threshold.py) | Own | as method comparisons do (Rojas-Labanda & Stolpe 2015) · [paper](https://doi.org/10.1007/s00158-015-1250-z) |
| Connectivity check | `connectivity` | [connectivity.py](postprocessors/connectivity.py) | Own | — |
| Feature size | `feature_size` | [feature_size.py](postprocessors/feature_size.py) | Own | measures what Sigmund 2007 and Wang et al. 2011 promise · papers [1](https://doi.org/10.1007/s00158-006-0087-x) [2](https://doi.org/10.1007/s00158-010-0602-y) |
| Grey level (M_nd) over the run | `grey_level` | [grey_level.py](postprocessors/grey_level.py) | Paper | Sigmund 2007 · [paper](https://doi.org/10.1007/s00158-006-0087-x) |
| Export outline (SVG), (DXF) | `export_svg`, `export_dxf` | [export_svg.py](postprocessors/export_svg.py), [export_dxf.py](postprocessors/export_dxf.py) | Own | — |
| Smooth outline (SVG + DXF) | `smooth_outline` | [smooth_outline.py](postprocessors/smooth_outline.py) | Paper | Subedi et al. 2020 (review); smoothing splines or Chaikin 1974 · papers [1](https://doi.org/10.1115/1.4047429) [2](https://doi.org/10.1016/0146-664X%2874%2990028-8) |
| Export solid (STL) | `export_stl` | [export_stl.py](postprocessors/export_stl.py) | Own | — |

### Benchmark problems ([folder](problems/README.md))

| In the app | File | From |
| :-- | :-- | :-- |
| MBB Beam | [mbb_beam.py](problems/mbb_beam.py) | the 99-line code and top88 · papers [1](https://doi.org/10.1007/s001580050176) [2](https://doi.org/10.1007/s00158-010-0594-7) |
| MBB Beam (Robust) | [mbb_beam_robust.py](problems/mbb_beam_robust.py) | Wang, Lazarov & Sigmund 2011 · [paper](https://doi.org/10.1007/s00158-010-0602-y) |
| Vibrating Beam | [vibrating_beam.py](problems/vibrating_beam.py) | after Du & Olhoff 2007 · [paper](https://doi.org/10.1007/s00158-007-0101-y) |
| Cantilever | [cantilever.py](problems/cantilever.py) | the 99-line code · [paper](https://doi.org/10.1007/s001580050176) |
| Nonlinear Cantilever | [nonlinear_cantilever.py](problems/nonlinear_cantilever.py) | Buhl, Pedersen & Sigmund 2000; Wang et al. 2014 · papers [1](https://doi.org/10.1007/s001580050089) [2](https://doi.org/10.1016/j.cma.2014.03.021) |
| Cantilever 3D | [cantilever_3d.py](problems/cantilever_3d.py) | top3d (Liu & Tovar 2014) · [paper](https://doi.org/10.1007/s00158-014-1107-x) |
| Michell Cantilever | [michell_cantilever.py](problems/michell_cantilever.py) | Michell 1904 · [paper](https://doi.org/10.1080/14786440409463229) |
| L-bracket (local stress) | [l_bracket_stress.py](problems/l_bracket_stress.py) | Giraldo-Londoño & Paulino 2021 (PolyStress); geometry of the L-bracket, limit chosen here · [paper](https://doi.org/10.1007/s00158-020-02760-8) |
| L-bracket | [l_bracket.py](problems/l_bracket.py) | Duysinx & Bendsøe 1998; Le et al. 2010 (dimensions still to be checked against the papers) · papers [1](https://doi.org/10.1002/%28SICI%291097-0207%2819981230%2943:8%3C1453::AID-NME480%3E3.0.CO%3B2-2) [2](https://doi.org/10.1007/s00158-009-0440-y) |
| Three-Point Bending | [three_point_bending.py](problems/three_point_bending.py) | the materials test |
| Heat Sink | [heat_sink.py](problems/heat_sink.py) | Bendsøe & Sigmund 2003, section 1.5; Gersborg-Hansen et al. 2006 · [paper](https://doi.org/10.1007/s00158-005-0584-3) |
| Standard Bar | [standard_bar.py](problems/standard_bar.py) | Toporia's own |
| Drone Arm, Drone Arm (Camera View), Drone Arm (Point Loads) | [drone_arm.py](problems/drone_arm.py), [drone_arm_camera_view.py](problems/drone_arm_camera_view.py), [drone_arm_point_loads.py](problems/drone_arm_point_loads.py) | Toporia's own application case |

---

## To add next

Listed from least to most effort. "Code" means open code exists (port it, or check against it).
"Paper" means it would be written from the paper. Details and status are in [TODO.md](TODO.md).

### Small: one file in an existing slot

| What | Kind | Source | Notes |
| :-- | :-- | :-- | :-- |
| Anisotropic PDE filter | filter | Paper: Lazarov & Sigmund 2011 · [paper](https://doi.org/10.1002/nme.3072) | a small extension of `pde` |
| Moving morphable voids (MMV) | representation | Paper: Zhang et al., *CMAME* 2017 · [paper](https://doi.org/10.1016/j.cma.2017.05.002) | holes instead of bars |
| Floating projection | optimiser | Paper: Huang, *Eng. Struct.* 2020 · [paper](https://doi.org/10.1016/j.engstruct.2020.110330) | binary designs without β continuation |
| Simulated annealing | optimiser | Code: topASA | a "why it loses" baseline |
| Compliant mechanism (output displacement) and the force-inverter benchmark | objective + problem | Paper: Sigmund 1997 · [paper](https://doi.org/10.1080/08905459708945415) | needs springs at input and output |
| pyMOTO's thermal, dynamic and mechanism modules | models | Code: [pyMOTO](https://github.com/aatmdelissen/pyMOTO) | already installed: the cheapest new physics |
| Reference results from the original MATLAB codes (top88, top99neo, top3d, TOBS, MMC, the level-set codes) | tests | Code: run once in GNU Octave or MATLAB · papers [1](https://doi.org/10.1007/s00158-010-0594-7) [2](https://doi.org/10.1007/s00158-020-02629-w) [3](https://doi.org/10.1007/s00158-014-1107-x) [4](https://doi.org/10.1007/s00158-020-02719-9) [5](https://doi.org/10.1007/s00158-015-1372-3) [6](https://doi.org/10.1007/s00158-018-1904-8) [7](https://doi.org/10.1007/s00158-014-1190-z) | proves the Python versions give the same answers |

### Medium: new physics or a whole method

| What | Source |
| :-- | :-- |
| Eigenfrequency, then linearised buckling | Code: TopBuck250 (Ferrari, Sigmund & Guest 2021) · [paper](https://doi.org/10.1007/s00158-021-02854-x) |
| Harmonic response | Code: PolyDyna · [paper](https://doi.org/10.1007/s00158-021-02859-6) |
| Heat conduction and thermal compliance | Paper: Bendsøe & Sigmund 2003; Gersborg-Hansen et al. 2006 · papers [1](https://doi.org/10.1007/978-3-662-05086-6) [2](https://doi.org/10.1007/s00158-005-0584-3) |
| Linearised buckling | Code: TopBuck250 (Ferrari, Sigmund & Guest 2021) · [paper](https://doi.org/10.1007/s00158-021-02854-x) |
| Local stress constraints with an augmented-Lagrangian optimiser | Code: PolyStress (Giraldo-Londoño & Paulino 2021) · [paper](https://doi.org/10.1007/s00158-020-02760-8) |
| Geometry projection (bars with round ends) | Code: GGP-Matlab, GPTO, pygpto (Norato et al.) · [paper](https://doi.org/10.1016/j.cma.2015.05.005) |
| Reaction–diffusion level set | Code: 88-line code of Otomori et al. 2015 · [paper](https://doi.org/10.1007/s00158-014-1190-z) |
| Hamilton–Jacobi level set; topological derivative | Code: Challis 2010; Amstutz & Andrä 2006 · papers [1](https://doi.org/10.1007/s00158-009-0430-0) [2](https://doi.org/10.1016/j.jcp.2005.12.015) |
| Phase field | Paper: Bourdin & Chambolle 2003; Takezawa et al. 2010 · papers [1](https://doi.org/10.1051/cocv:2002070) [2](https://doi.org/10.1016/j.jcp.2009.12.017) |
| Explicit length-scale constraints, machining accessibility, projection-based self-support | Paper: Zhou et al. 2015; Langelaar 2019; Gaynor & Guest 2016 · papers [1](https://doi.org/10.1016/j.cma.2015.05.003) [2](https://doi.org/10.1016/j.cma.2019.03.037) [3](https://doi.org/10.1007/s00158-016-1551-x) |
| Multi-resolution design and analysis meshes | Paper: Nguyen et al. 2010 · [paper](https://doi.org/10.1007/s00158-009-0443-8) |
| Neural reparameterisation (TOuNN) | Code: TOuNN (needs PyTorch or JAX, which may not install on Python 3.14) · [paper](https://doi.org/10.1007/s00158-020-02748-4) |
| SINH and Hashin–Shtrikman material laws | Paper: Bruns 2005; Bendsøe & Sigmund 1999 (the material law has to see the volume and Poisson's ratio) · papers [1](https://doi.org/10.1007/s00158-005-0537-x) [2](https://doi.org/10.1007/s004190050248) |

### Large: the framework has to change first

| What | Unlocks |
| :-- | :-- |
| Several fields per element | DMO, fibre orientation, true multi-material |
| Unstructured meshes | PolyTop/PolyMesher, VEM, FEniTop, CAD import |
| Beam and truss elements | ground structures (GRAND), Michell layouts |
| Multiscale, IGA, CutFEM | de-homogenisation (deHomTop808), IgaTop, GridapTopOpt |
| Fluids, transient, acoustics, photonics | topflow, TOFLUX, ceviche, Meep |
| Learned methods | TopoDiff, TopologyGAN, dl4to and the SELTO datasets |

### Blocked for now

| What | Why |
| :-- | :-- |
| IPOPT (`cyipopt`) | no Windows build for Python 3.14; would need conda or an older Python |
| ParOpt | not on PyPI |
| TOFLUX | the repository states no licence, so it cannot be reused |
| MATLAB bridge (run the originals as whole methods) | the MATLAB Engine for R2026a supports Python ≤ 3.13; GNU Octave is the free alternative |
