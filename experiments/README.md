# Research experiments and validation recipes

## Fixed projection without beta continuation

`python -m experiments.fixed_projection --iterations 600 --mesh 1` runs the
`MBB Beam (Fixed Projection)` recipe on MBB and cantilever, prints final physical
measurements and saves no run outputs. GUI/CLI users can select the preset directly.
This is an independent recipe using existing density, tanh Heaviside and MMA parts.
The full Guest-Asadpoure-Ha (2011) paper remains subscription-only; its other
projection/optimizer variants have not been reproduced.

The readable parameter source is [Høghøj & Träff §3.1, eq. (11)](https://arxiv.org/html/2102.12999#S3.SS1):
initial asymptote spacing `0.5/(2*beta+1)`, growth 1.05, shrink 0.65 and move 0.1.
Here beta=beta_max=16 throughout, with no schedules. This differs from that paper's
machining projection and uses Toporia's own one-constraint MMA scaling. GUI asymptote
precision retains the small initial spacing. Default optimizer behavior is unchanged.

| Preset / mesh | Initial C | Final C | Physical volume / limit | Gray cells (0.1–0.9) | Last change |
| :-- | --: | --: | :-- | --: | --: |
| MBB, 60×20 | 1007.02210 | 197.12351 | 0.500000 / 0.5 | 1.00% | 0.0001642 |
| Cantilever, 60×30 | 658179.74724 | 81.28574 | 0.400000 / 0.4 | 0.89% | 0.0002181 |

Both ran exactly 600 steps. Neither meets MMA's stricter 1e-4 change tolerance;
gray indicators `mean(4*rho*(1-rho))` are 0.01007 and 0.01119. Constant projection
does not guarantee binary solutions, global optima, manufacturing length scales or
stability with arbitrary updaters. The low-volume cantilever starts with a very soft
projected uniform field; its large improvement should be read with that in mind.
Three focused tests cover fixed beta over 600 iterations, physical budgets and
objective improvement on two small meshes. GUI round-trip/comparison checks also
cover the preset. Broader reference: [Guest et al. (2011)](https://doi.org/10.1007/s00158-011-0676-1).

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
| pyMOTO GCMMA / 1000 | MBB | 12522.25648 | 391.36346 | 0.499992 / 0.5 | 20.08% | 0.01428 |
| pyMOTO GCMMA / 1000 | Cantilever | 2901.78844 | 284.11337 | 0.399995 / 0.4 | 16.56% | 0.01231 |

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

The longer GCMMA check uses the same settings and reproduces the 500-step
baseline before continuing to 1000. Objectives improve, but neither run settles.
At cutoff 0.5, volumes are 0.516667 / 0.409444 and each field has one unsupported
cell in the independent one-layer test. The script now also chooses a strict
cell-count cutoff that respects the smooth-design budget, then re-solves physics:

| 1000-step GCMMA | Cutoff (`rho > cutoff`) | Binary volume | Fresh binary C | Unsupported cells |
| :-- | --: | --: | --: | --: |
| MBB | 0.554823 | 0.500000 | 319.60022 | 0 |
| Cantilever | 0.532182 | 0.400000 | 235.27987 | 0 |

Equal-valued cutoff cells are excluded, so ties cannot exceed the cell-count
budget. This is a diagnostic post-processing threshold, not a geometry repair
or a general guarantee: thresholding can remove supports on other designs.
These two binary fields pass the stated budget and stencil checks only; point
hinges, stress, nonlinear response and the actual printing process are unchecked.
All 21 geometric/adjoint tests pass. No core self-support formula was changed.

## Original MATLAB references

The reusable read-only prerequisite check is
`python -m experiments.original_references --audit-matlab --matlab-exe "C:\Program Files\MATLAB\R2026a\bin\matlab.exe"`.
It reports runtime, Optimization Toolbox licence, helper locations and selected
C compiler using an automatically removed temporary directory. It never installs,
selects a compiler, saves a MATLAB path or changes persistent settings.

| Remaining original | Latest evidence (27 October) | Next requirement |
| :-- | :-- | :-- |
| top99neo / top3D125 | Unchanged author sources run; bounded trajectories recorded; top3D125 initial H8 FE agrees at printed precision | Complete for these scopes; not equality of optimizer trajectories |
| MMC188 | Published appendix found; identified GPL MMA helper with embedded subsolv now available outside repo; byte-identifiable runnable MMC source still absent | Obtain identifiable original MMC source; no claim of original-code equality |
| TOBS101 | Unmodified source errors on removed intlinprog `CutGeneration`; modern-options copy reaches cap with very poor C | Compatibility attempt rejected; original-runtime validation remains blocked |
| Challis HJ/TD | Unchanged publisher source converges in 55 steps; initial/final-field Q4 FE agree | Complete for native run and FE check; not HJ trajectory equality |
| Otomori reaction-diffusion | Author code host remains inaccessible | Obtain identifiable original source |

Numerical agreement is limited to the explicitly stated scopes below. The
approved portable compiler/helper setup is completed under
`C:\Users\johan\AppData\Local\ToporiaValidation`. GCC 14.2's archive matches
its publisher checksum. Unmodified fsparse builds with the separate-complex API
and passes three seeded random duplicate-index assemblies and an exact fixture
against native `sparse`. Setup used a separate R2026a preferences directory and
process-local `MW_MINGW64_LOC`/`MATLAB_PREFDIR`. Global PATH, saved MATLAB path and
normal default compiler were not changed. Source/binary hashes are in the fixture.
The compiler download archive was removed after extraction; reusable tools,
original author sources and licences remain outside the repository.

The owner personally installed the licensed Image Processing Toolbox after the
agent's signed, R2026aU5-pinned installer was refused Windows elevation/write access.
Read-only verification confirms unchanged R2026a Update 5, available imfilter,
bwdist and padarray, and no compiler selected in normal MATLAB preferences.
The external fsparse/MMA helpers are absent from the saved global path.

### Captured native MMA reference

`python -m experiments.original_references --mma` repeats the optional mmapy
port on a convex six-variable reciprocal objective against a captured MATLAB
run. The GPL source is an identified distribution copy with preserved Svanberg
copyright and embedded `subsolv`, not a direct author-site download. No source
is bundled here. Both first and 30th designs, objective, multiplier and budget
agree within 1e-10. Fresh final objective is **63.4965945463**, budget
**2.39999999648** against 2.4; analytic optimum is **63.4965944531**.
The initial design is over budget, so its lower objective is not a feasible
performance comparison. The fixture records the full problem, source revision
and SHA-256 hash. This validates mmapy's port, not equality of Toporia's own
distinct one-budget MMA approximation. The existing `--matlab` driver still
reruns the three FE references; it does not replay this standalone optimizer capture.

Unmodified author-distributed functions were run with MATLAB R2026a Update 5
on 27 October 2026. [`tests/references/matlab.json`](../tests/references/matlab.json)
records commands, source SHA-256 hashes, runtime and observations. The original
sources are not bundled. Reusable author sources remain in the isolated external
validation folder; scratch traces, figures and fields are removed after validation.
Existing internal golden baselines are unchanged.

| Original command | Iterations | First printed C | Last printed C | Printed volume |
| :-- | --: | --: | --: | --: |
| `top88(24,8,0.5,3,1.5,1)` | 39 | 975.8323 | 265.3387 | 0.500 |
| `top88(24,8,0.5,3,1.5,2)` | 56 | 975.8323 | 274.4604 | 0.500 |
| `top3d(12,4,2,0.3,3,1.5)` | 39 | 18934.5908 | 7549.3805 | 0.300 |

Toporia matches these iteration counts and first/last objectives within half a
printed four-decimal unit. Both top88 final mean densities also match within
1e-10. These objectives precede the last update; they must not be labelled fresh
final-design compliances. Top3d applies a unit force at every tip-bottom depth
node. The Python reference recipe explicitly sets equal nodal shares and total
force 3, rather than changing production trapezoidal line-load integration.

Run `python -m experiments.original_references` for the Python comparison.
To repeat the actual originals, download `top88.m` and `top3d.m` from the fixture's
source URLs into a separate folder, then run
`python -m experiments.original_references --matlab --source-dir PATH`.
Use `--matlab-exe PATH` if MATLAB is not on PATH. The recipe verifies hashes,
copies the two files to an automatically removed temporary directory, disables
figure visibility, and prints observations. It installs nothing, changes no
MATLAB saved path, and never regenerates fixtures automatically.

The publisher's unmodified [TOPRBF supplement](https://doi.org/10.1007/s00158-018-1904-8)
also completed `TOPRBF(40,20,0.5)`: 88 iterations, C=594277.942780,
volume=0.499728. Its initial C=585921.079450 and volume=0.835408 use a -100 tip
force. This is a standalone reference, not a strict oracle for Toporia's numerical
variant: mean energy normalisation, guarded rescaling, field clipping and sampling
details differ. Toporia's corresponding initial C=585978.138686 and fraction
0.835374 already show a small sampling difference. An original 24x8 attempt lost
finite level-set values and became empty; that attempt is rejected, not accepted
as a successful reference. Only documentation/citation was corrected in the
existing Python RBF method; no algorithm or golden baseline was changed.

### Newly unblocked native cases

| Original / command settings | Steps | First printed C | Last printed C | Last volume |
| :-- | --: | --: | --: | --: |
| top99neo, 24x8, vf=.5, density, zero-padding, 20-step cap | 20 | 975.8323 | 316.1767 | 0.497 |
| top99neo, same grid, volume-preserving projection beta=8 | 20 | 975.8323 | 5121.8397 | 0.500 |
| top3D125, 12x4x2, vf=.3, density, zero-padding, 20-step cap | 20 | 40809.0 | 12683.4 | 0.309 |
| Challis `top_levelset(24,12,.5,2,10,2)` | 55 | 5.8464 | 8.1996 | 0.500 |

Exact commands and source hashes are in the fixture. The neo cases are bounded
observations, not converged or paper-performance reproductions. High-beta top99neo
still oscillates (change 0.423), and top3D125 exceeds its 0.3 physical budget.
Toporia's 20-step density/OC case gives C=311.76497 and volume=0.499918;
different OC bisections and design-versus-physical budget conventions prevent
treating the neo trajectory as a strict equality oracle.

`python -m experiments.original_references --additional-fe` checks the additional
finite-element scopes. Top3D125's initial response uses the author's exact
front-face sine z forces, not a distributed-depth load. Toporia gives 40808.98084,
matching the original `%6.5e` precision (0.1 at this magnitude). Challis uses
both constrained DOFs at its two endpoint nodes and the exact centre-node force;
Toporia gives initial/final-field C=5.84641029 / 8.19962980 and volume 0.5.
The final field is captured before the converged return, so the printed C applies
to that exact stored binary field. These verify FE responses, not equality of
Toporia's independent level-set optimization trajectory.

The separate TOBS compatibility copy only renames the function, drops unsupported
intlinprog options while retaining MaxNodes=1e5/Display=off, adds a 200-step cap
and normalizes newlines. At the cap it reports C=1.558315e10, volume=0.5 and
change=0.037. This very poor, unconverged result is rejected; no source or solver
change is hidden behind an original-code agreement claim. The unchanged source
and compatibility hashes are recorded separately. No production TOBS math changed.

Remaining original-reference gaps are explicit:

- MMC188 still lacks an identifiable runnable author file; a published appendix
  is available and the external MMA helper is now available. No result is fabricated.
- Original TOBS101 reaches an R2026a error: `Option "CutGeneration" for intlinprog has been removed.`
  Its separately labelled compatibility run above fails the quality/stability check.
- The reaction-diffusion author's source host remains unavailable; no byte-identifiable
  original file was recovered. Published-code transcriptions are not called unchanged originals.

No runtime/compiler/toolbox is installed or reconfigured without the owner's
approval. All seven reference regression checks pass within their stated scopes;
method variants are not claimed to reproduce all reference papers.

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

### Stronger projection and mesh-transfer check

`python -m experiments.neural --iterations 1000 --mesh .5 --updater mma --beta 16 --seed 0 --settle-move .0001`
runs an intentionally bounded fixed-projection attempt. Repeat with `--seed 1`.
Beta remains 16; the final 40% of iterations reduce the weight move from 0.005
to 0.0001. This is a recorded failure case, not a recommended binary-design recipe.

| Seed / preset | Fresh C | Volume | Gray cells | Last physical change | Finer-grid C |
| :-- | --: | --: | --: | --: | --: |
| 0 / MBB | 395.93920 | 0.50000002 | 91.00% | 0.0001507 | 399.78818 |
| 0 / Cantilever | 287.15891 | 0.39999871 | 95.33% | 0.0054584 | 287.66119 |
| 1 / MBB | 384.52250 | 0.49999973 | 89.00% | 0.0001822 | 389.24750 |
| 1 / Cantilever | 326.97750 | 0.40000014 | 100.00% | 0.0004257 | 336.59210 |

The same learned weights are evaluated at twice the grid resolution without
training; filter radius doubles in cells to keep its physical size. Finer-grid
cantilever volumes are 0.40008499 / 0.40005908: small budget violations remain.
Volume-limited strict thresholding gives only 20.4–31.7% solid volume and
compliances of 2.39e8–4.00e9, exposing disconnected/soft-background-dependent
designs. Neither seed gives useful binary topology or convergence certification.

Without `--settle-move`, seed 0 has physical changes 0.1364 / 0.3208 despite
weight changes of only 0.005, with 90.3% / 91.3% gray cells. The cantilever
volume is 0.40290 against 0.4. This exposed a real stopping issue: neural
representations now opt into physical-change monitoring. The composed method
reports the larger of variable and physical-density change, preventing tiny
weight steps from hiding substantial physical motion. This does not turn a
stationary gray design into a binary optimum. Eighteen focused tests include
the sharp-projection adjoint and the premature-stopping regression.

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

Run `python -m experiments.minimum_length` to print the report without creating
files. Add `--out results/minimum-length-validation` explicitly to save initial/final
density, `report.json` and `validation.png`.
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

The stronger check re-evaluates cutoff-0.5 binary fields and repeats each cell
twice per axis for a 48x32 grid with the same physical 4 mm target. It changes
no constraint tolerance and performs no finer-grid optimization:

| Feasible-seed final field | C | Volume | Solid residual | Void residual |
| :-- | --: | --: | --: | --: |
| Coarse smooth | 111.90787 | 0.500000 | -2.22e-7 | -3.23e-8 |
| Coarse binary | 116.34435 | 0.500000 | -0.03875 | -0.03875 |
| Finer smooth | 113.15650 | 0.500000 | +13.86719 | +12.80328 |
| Finer binary | 117.60605 | 0.500000 | -0.30642 | -0.30642 |

The binary field passes both proxies on both grids. The optimized gray field
does not transfer feasibility: the nodal tolerance scale tightens with mesh
resolution and remaining intermediate densities violate it on refinement.
This is a significant limitation of this calibrated physical-field proxy, not
an exact continuum size certificate. The optimizer's local smooth gain does not
survive binarization as an improvement over the original straight-bar concept.

`python -m experiments.minimum_length --start uniform` records the uniform-start
failure and exits nonzero because it is infeasible. NLopt reports FTOL_REACHED
after two evaluations, but both coarse residuals remain **+13.87811**; the
independent feasibility flag is false. On the finer grid they are **+235.54980**.
Thresholding that exactly gray field produces no material and enormous compliance;
passing geometric proxies alone therefore says nothing about load-bearing ability.
All 21 analytical, geometry, adjoint and feasible-seed tests pass. No core response
formula, numerical baseline or tolerance was changed by this validation.

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
