# Unregistered experiments

These are reproducible research evaluations, outside Toporia's plugin discovery
and GUI. Failed performance gates are recorded rather than weakened.

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
