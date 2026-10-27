# Research experiments and validation recipes

These are reproducible research evaluations, outside Toporia's plugin discovery
and GUI. Failed performance gates are recorded rather than weakened.

## Machining accessibility

`python -m experiments.machining --iterations 80` prints measurements without saving runs. It uses
24×8 Q4 and 24×8×4 H8 grids, a top-side tool, a radius-1.5 density filter and
small-move MMA. The source start is calibrated to the physical volume budget.
Each final objective is reevaluated after the final update.

| Preset | Initial compliance | Final compliance | Physical volume | Inaccessible thresholded void cells |
| :-- | --: | --: | --: | --: |
| MBB Beam | 217476025.72 | 686.42380 | 0.499864 / 0.5 | 0 |
| Cantilever 3D | 648.33247 | 76.06831 | 0.299961 / 0.3 | 0 |

The MBB start is particularly weak because its upper load point lies near the
tool's entry face. These are bounded integration benchmarks, not converged
paper reproductions: final maximum changes are 0.04979 and 0.01 respectively.
Gray fractions between 0.1 and 0.9 are 18.75% and 3.91%. The independent ray
check uses a 0.5 density threshold and the selected Cartesian tool side; it
does not certify a finite cutter or holder. The PDE has known diffusion and
projection artefacts. See the [filter scope](../toporia/plugins/filters/README.md#machining-accessibility).

## Projection-based self-support

`python -m experiments.self_support --iterations 1000 --mesh 1` uses the
registered cell-centred projection, a bottom build plate, 45° support angle,
radius 2.4 cells and support threshold 0.1. It prints progress and a final report;
no run files are written. The 60×20 MBB and 60×30 cantilever grids resolve
the features much better than 24-cell-wide smoke meshes, which retained 63–89%
gray material in the tested short/continued runs.

RAMP q increases 10→20→30 every 200 iterations. Local projection sharpness
increases 10→25 after 50; support sharpness stays 20. Own MMA starts with
move 0.01, asymptotes 0.02, expansion 1.05 and contraction 0.65; after 400
iterations its move falls to 0.0005. The GUI and parameter schema now preserve
these small values without changing the existing 0.2 default.

With the already optional pyMOTO dependency, run
`python -m experiments.self_support --iterations 500 --mesh 1 --updater pymoto_gcmma`.
That wrapper fixes its move at 0.01 and uses conservative inner trial checks;
the unsupported move schedule is omitted explicitly. Both variants use the same
material and projection continuation. The initial physical design is reevaluated
at the final q=30 so the initial/final compliances use the same material law.

| Updater / iterations | Preset | Initial compliance | Final compliance | Physical volume / limit | Gray fraction 0.1–0.9 | Final maximum change |
| :-- | :-- | --: | --: | --: | --: | --: |
| Own MMA / 1000 | MBB | 12522.25648 | 484.89162 | 0.499837 / 0.5 | 16.67% | 0.10972 |
| Own MMA / 1000 | Cantilever | 2901.78844 | 324.62781 | 0.399862 / 0.4 | 14.89% | 0.15345 |
| pyMOTO GCMMA / 500 | MBB | 12522.25648 | 454.66344 | 0.499995 / 0.5 | 20.50% | 0.02508 |
| pyMOTO GCMMA / 500 | Cantilever | 2901.78844 | 296.54728 | 0.399999 / 0.4 | 15.83% | 0.01052 |

These are bounded improvement/feasibility runs, **not convergence claims** or
timing comparisons. Small moves alone do not eliminate the projection's strong
nonlinearity. The independent one-layer 45° test on the 0.5-thresholded physical
field finds 1/2 unsupported cells for own MMA and 0/1 for GCMMA (MBB/cantilever).
This stencil is stricter than the multi-layer wedge in some locations, but the
discrepancy must still be inspected before fabrication.

Thresholding changes the volume: own MMA gives 0.5125/0.407222 and GCMMA gives
0.519167/0.411111. All four exceed their smooth-design budgets after thresholding.
Fresh binary-field compliances are 385.85622/269.24762 and 347.78378/240.99253,
respectively; they are not budget-matched performance comparisons. No binary
result is labelled feasible or printable. The [filter documentation](../toporia/plugins/filters/README.md#gaynorguest-self-support-projection)
describes the cell discretisation, boundary truncation and grid-dependent threshold.

## Hashin-Shtrikman upper envelope

Run `python -m experiments.material_laws --law hashin_shtrikman --iterations 300 --mesh 1`.
This uses the scenario nu=0.3, Emin=1e-9, both fixed-nu HS upper-channel limits,
MMA move 0.05 and density radius 1.5. Final physical responses are recomputed;
the recipe saves no files. Geometric and budget volume are identical for this law.

| Preset | Initial C | Final C | Volume / limit | Gray 0.1-0.9 | Last change |
| :-- | --: | --: | --: | --: | --: |
| MBB | 513.19396 | 199.62258 | 0.499988 / 0.5 | 34.83% | 0.002999 |
| Cantilever | 222.04768 | 83.15603 | 0.399769 / 0.4 | 26.72% | 0.050000 |

Both reach the 300-step cap, improve compliance and fit their budgets. They
are not convergence or binary-design claims. The envelope satisfies both elastic
upper limits at the solver's fixed nu. It neither implements the paper's variable
nu nor certifies lower bounds, joint attainability or a manufacturable composite.
The common SIMP p=3 comparison referee also uses a different interpolation.
See the [material-law scope](../toporia/plugins/interpolations/README.md#hashin-shtrikman-fixed-nu-upper-envelope).

## SINH effective volume

Run `python -m experiments.material_laws --iterations 300 --mesh 1`.
This uses basic SINH p=3 with shared density filtering (radius 1.5), MMA move
0.05 and fresh final Q4 evaluations. No run files are saved. The geometric
field and effective cost use different measures, as in Bruns Table 2 case 5.

| Preset | Initial C | Final linear-material C | Geometric fraction | Effective cost / limit | Gray 0.1-0.9 | Last change |
| :-- | --: | --: | --: | --: | --: | --: |
| MBB | 550.63805 | 202.79554 | 0.414981 | 0.500000 / 0.5 | 33.75% | 0.007759 |
| Cantilever | 234.23086 | 84.58895 | 0.337000 | 0.398823 / 0.4 | 27.22% | 0.038767 |

Both runs reach the 300-step cap, improve compliance and meet effective budgets.
They remain gray and are not convergence or paper-reproduction claims. SINH's
linear stiffness and taxed cost cannot be compared directly with a SIMP p=3
objective at the same geometric fraction. Compare Methods still uses its common
SIMP p=3 referee and additionally records the actual effective volume. The
resource-only filtered and hybrid formulations from the paper are not implemented.

## Neural coordinate field

Run `python -m experiments.neural --iterations 600 --mesh 0.5 --updater adam`
or choose `--updater mma`. The independent smooth TOuNN-style NumPy network has
two tanh layers of width 20, sigmoid output, seed 0 and 501 trainable weights/biases.
Adam uses lr 0.01 and decay 0.995; MMA uses move 0.005. Both use SIMP p=3 and
density radius 1.5. The recipe prints fresh final evaluations and saves no files.

| Updater / preset | Initial C | Final C | Physical volume / limit | Gray fraction 0.1-0.9 | Last weight change |
| :-- | --: | --: | --: | --: | --: |
| Adam / MBB | 984.55480 | 389.76771 | 0.499926 / 0.5 | 83.33% | 0.000841 |
| Adam / Cantilever | 609.61732 | 192.14204 | 0.399894 / 0.4 | 64.89% | 0.000682 |
| MMA / MBB | 984.55480 | 346.15640 | 0.499657 / 0.5 | 82.33% | 0.005000 |
| MMA / Cantilever | 609.61732 | 144.21322 | 0.399825 / 0.4 | 38.00% | 0.005000 |

All stop at the 600-step cap; these are improvement and smooth-budget checks,
not convergence, crispness, performance parity or reproduction of original TOuNN.
In particular the MBB retains mostly gray material. Network size/seed, finite
weight bounds, tanh activation and the existing optimisers differ from the
reference's batch-normalised LeakyReLU/AMSGrad procedure. No original GPL code
is copied and no PyTorch/JAX dependency is installed. The full chain uses actual
Q4 solves; the network represents the density, rather than replacing physics.

<a id="multiresolution-analysis"></a>

## Multiresolution: coarse analysis, fine density

Run `python -m experiments.multiresolution --iterations 100 --mesh 1 --radius 3`.
This compares reference factor 1 and coarsening factor 2 on the same fine design
grid, density filter, material and OC settings. It prints measurements without
writing run outputs. Every final field receives a fresh, independent fine-Q4 solve.

| Preset / factor | Free system DOFs | Analysis compliance | Fine-Q4 compliance | Physical volume / limit | Optimisation seconds |
| :-- | --: | --: | --: | --: | --: |
| MBB / 1 | 2540 | 249.35203 | 249.35203 | 0.499996 / 0.5 | 2.125 |
| MBB / 2 | 670 | 244.09112 | 249.59705 | 0.500019 / 0.5 | 1.099 |
| Cantilever / 1 | 3720 | 110.01908 | 110.01908 | 0.399984 / 0.4 | 3.884 |
| Cantilever / 2 | 960 | 108.08059 | 110.14153 | 0.399985 / 0.4 | 1.675 |

These are bounded 100-step runs, not convergence claims. Timings are illustrative
single runs with one BLAS thread. Factor 2 underestimates fine compliance by
2.21% / 1.87%; the MBB volume has a small OC bisection overshoot. A deliberately
disconnected fine-density test also demonstrates that coarse interpolation can
bridge a void cut. Density filtering does not certify removal of these artefacts.
Compare Methods always retains its independent fine-Q4 referee.

The model uses exact fine-cell quadrature of coarse bilinear displacement fields,
projected loads and constrained interpolation of fine supports. This is an aligned
2-D variant of the [MTOP paradigm](https://doi.org/10.1007/s00158-009-0443-8),
not its original centroid-rule implementation, adaptive/high-order analysis or
independent three-mesh system. See the [model documentation](../toporia/plugins/models/README.md#multiresolution-q4)
and [QR-pattern study](https://doi.org/10.1007/s00158-018-2048-6).

## Minimum-length response: feasible-seed validation

Run `python -m experiments.minimum_length` to write initial/final density,
`report.json` and `validation.png` to `results/minimum-length-validation/`.
This exercises the registered geometric response with NLopt MMA on a 24x16
cantilever, 4 mm solid and void proxy targets and volume 0.5. It explicitly
seeds a nearly binary straight bar using the identity representation. It uses
linear ersatz interpolation, not penalised SIMP. The GUI does not acquire a
file warm-start feature through this script.

Fresh final evaluations give compliance 111.907874 (initial 115.115877), volume
0.4999999991 and solid/void residuals -2.22e-7/-3.23e-8. Feasibility is checked
independently of the optimiser's stopping status. This modest local validation
does not establish a robust optimiser from a uniform gray start: strict two-phase
constraints stalled NLopt there, and a 700-step pyMOTO GCMMA continuation on the
60x20 MBB, 6 mm target, retained a +0.953 solid violation. That run is **not**
accepted as a feasible result. See the response documentation for discretisation,
gray-field, exterior-boundary and tolerance limitations.

## Simulated annealing: evaluated, not registered

Run from the repository root:

```
python -m experiments.simulated_annealing --budgets 200 2000 --seeds 0 1 2
```

The script writes `report.json` and physical-density NumPy arrays under
`results/annealing-evaluation/`. The solve budget includes the initial evaluation.
No physics gradients are requested. This is an own standard Metropolis baseline
with random pair transfers, geometric cooling and a scalar volume repair.
Best-so-far history is retained. Volume repair uses cheap model-volume checks,
which still cost CPU time; solve counts alone are not wall-time comparisons.

The [topASA repository](https://github.com/Hossein-Rostami/Topology-Optimization-with-adaptive-Simulated-Annealing)
has no stated licence (checked 25 October 2026). No MATLAB code was copied.
This experiment does **not** reproduce or evaluate adaptive topASA, and its
outcome is not a conclusion about all annealing methods.

### Measured result

Standard MBB conformance scenario: 24 × 8 Q4 elements (`m=0.4`), the preset's
SIMP law and density filter, volume limit 0.5, uniform start. OC under the
unchanged 0.01 design-change tolerance reaches compliance **274.46963** in
**57 solves**, including the final evaluation. The existing acceptance limit is
10% above that compliance, approximately **301.917**.

| SA solve budget | Seed | Best compliance | Above OC | Volume |
| --: | --: | --: | --: | --: |
| 200 | 0 | 794.1730 | 189.35% | 0.5000 |
| 200 | 1 | 809.1554 | 194.81% | 0.5000 |
| 200 | 2 | 816.4796 | 197.48% | 0.5000 |
| 2000 | 0 | 380.8954 | 38.78% | 0.5000 |
| 2000 | 1 | 391.3186 | 42.57% | 0.5000 |
| 2000 | 2 | 393.2443 | 43.27% | 0.5000 |

All six runs respect budgets, bounds and physical volume. All miss the unchanged
performance gate, including at 2000 solves (35 times OC's solve count).
Consequently **no annealing updater is registered**. This bounded evaluation is
complete; further tuning or a licensed adaptive-SA port is a distinct research task.

Eight tests check the solve cap, value-only evaluations, reproducibility,
monotone best history, bounds, pins and absence from the registry:
`python -m pytest tests/checks/test_annealing_experiment.py`.

References: S. Kirkpatrick, C. D. Gelatt Jr., M. P. Vecchi, *Science* 220 (1983)
671–680, [DOI](https://doi.org/10.1126/science.220.4598.671). O. Sigmund,
"On the usefulness of non-gradient approaches in topology optimization", *SMO*
43 (2011) 589–596, [DOI](https://doi.org/10.1007/s00158-011-0638-7).
