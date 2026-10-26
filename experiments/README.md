# Research experiments and validation recipes

These are reproducible research evaluations, outside Toporia's plugin discovery
and GUI. Failed performance gates are recorded rather than weakened.

## Machining accessibility

`python -m experiments.machining --iterations 80` prints JSON only. It uses
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
