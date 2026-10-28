# Post-processors: what is made of a finished design

An optimisation ends with a density field. What gets reported, compared and manufactured
is made from that field afterwards. A post-processor does one such job; see
[`framework/parts/postprocess.py`](../../framework/parts/postprocess.py).

**Switching them on.** Each post-processor is switched on by listing it in the run's Output
section. Any combination works, in the order given:

```python
output.postprocess = [{"type": "threshold"}, {"type": "connectivity"}, {"type": "export_dxf"}]
```

- **GUI:** the **Post-processing** panel. The post-processors also appear in the Pipeline box.
- **Command line:** `--set 'postprocess=[{"type": "threshold"}]'` on any run.

**Outputs.**
- Files go to `<run folder>/post/`.
- The numbers are printed, and written to `run.json` under `"postprocess"`.
- In **Compare Methods** and the benchmark, the post-processors run on every method's
  design the same way, and their numbers become extra columns, e.g. `threshold.compliance`.
  The referee compliance column stays as before.

A post-processor that fails is reported, and the run and the other post-processors are
kept. To apply post-processors to a run saved earlier without optimising again:

```bash
toporia post results/my_run threshold connectivity export_stl:thickness=3
```

**In 3-D**: threshold, grey level, connectivity (pieces share a face), feature size and the STL solid work;
the images show the design as seen through its depth. The SVG, DXF and smoothed outlines are 2-D only.

**Status: 8 in Toporia · 0 with open code · 1 paper only**

| Label | Meaning |
| :-- | :-- |
| ✅ **In Toporia** | Implemented here, registered, passes `toporia check postprocessor:<name>`. |
| 🔗 **Open code** | A public implementation exists to port or check against. |
| 📄 **Paper only** | Would be written from the paper. |

## ✅ In Toporia

| Post-processor | File | Name | What it gives |
| :-- | :-- | :-- | :-- |
| ✅ Threshold | [`threshold.py`](threshold.py) | `threshold` | Black and white at the original volume (or at a fixed level), with holes kept. The compliance of that design, measured by the referee (Q4, SIMP p = 3, no filter), next to the grey design's compliance. Methods finish with different amounts of grey, so this is the number papers compare. Later post-processors use this design. |
| ✅ Connectivity | [`connectivity.py`](connectivity.py) | `connectivity` | The pieces of the black-and-white design, the share of material touching no support, and whether every load reaches a support. Elements touching only at a corner do not count as joined. `connectivity.png` shows floating material in red. |
| ✅ Feature size | [`feature_size.py`](feature_size.py) | `feature_size` | The thinnest member and the smallest hole, in mm, from the distance to the other phase along the middle of each member. Good to about one element; an even width reads one less. |
| ✅ Grey level over the run | [`grey_level.py`](grey_level.py) | `grey_level` | Sigmund's measure of non-discreteness M_nd = 4/n Σ ρ(1−ρ), in percent (0 for black and white, 100 for uniform half-density): the final value, the first and the peak, and the curve over the iterations as `grey_level.png` and `.csv` |
| ✅ SVG outline | [`export_svg.py`](export_svg.py) | `export_svg` | The outline in mm, for figures |
| ✅ Smoothed outline | [`smooth_outline.py`](smooth_outline.py) | `smooth_outline` | The outline fitted with smooth curves instead of the element-grid contour, as `design_smooth.svg` and `design_smooth.dxf` in mm. 2-D only |
| ✅ DXF outline | [`export_dxf.py`](export_dxf.py) | `export_dxf` | Closed R12 polylines in mm, for CAD and laser or waterjet cutting |
| ✅ STL solid | [`export_stl.py`](export_stl.py) | `export_stl` | The black-and-white design extruded to a thickness: one closed binary STL in mm, stepped at the element size, for 3-D printing |

**Outlines** are contours of the density at the level the black-and-white design was cut at.
A design with explicit geometry exports that geometry instead (`source = auto`). For moving
morphable components that geometry is the bars themselves, uncut by the domain edge or by
holes. `source = contour` exports the design as analysed.

**What a threshold can reveal.** Thin grey members, which are common with optimality criteria
and a small filter radius, can break apart when cut to black and white. They become chains
of elements that touch only at corners. Connectivity then reports them as floating, and
feature size reports a one-element member. The grey design looked fine; the manufacturable
one is not.

## Measure of non-discreteness over the run

**What.** `grey_level` reports M_nd = 4/n Σ ρ(1−ρ) × 100 % (Sigmund, *SMO* 33 (2007) 401–424)
on the final physical density, and, when it runs straight after an optimisation, over every
iteration: `grey_level.csv` and `grey_level.png`. The metrics are `final_pct`, `first_pct`,
`peak_pct` and `iterations`; `final_pct` and `peak_pct` become comparison columns.

**When.** To see whether a method or a projection continuation really reaches black and
white, and when; the final value alone hides a design that was grey for most of the run.

**Per-iteration values** are recorded by the loop (`ResultStore.grey_levels`, a few arithmetic
operations on the density already at hand; nothing else in `run.json` or the histories
changes). A run loaded from a saved folder keeps no history, so `toporia post` gives only the final value.

**Use.** In a config: `output.postprocess = [{"type": "grey_level"}]`. In the GUI: Post-processing
panel, "Grey level (M_nd) over the run". Command line:

```bash
toporia run "MBB Beam" --out results/mbb --set 'postprocess=[{"type": "grey_level"}]'
```

## Smoothed outlines

**What.** `smooth_outline` takes the contour of the density at the level of the black-and-white
design (the contour `export_svg` writes) and replaces each closed loop with a smooth curve:
a periodic smoothing spline (`method = spline`, the default, which may move the contour by
`tolerance` element sizes), or Chaikin corner cutting (`method = chaikin`, `passes` times).
After Subedi et al., *J. Comput. Inf. Sci. Eng.* 2020. Points are clipped to the domain.

**When.** For figures and for CAD or cutting, where stair-steps from the element grid are
unwanted. The curves are many short segments; they are not exact geometry, only close to
the design (within about an element). 2-D only; a 3-D design is refused.

**Files.** `design_smooth.svg` and `design_smooth.dxf`, in mm, written with the same code
as the plain exporters. Metrics: `outlines`, `points`.

**Use.** In a config: `output.postprocess = [{"type": "smooth_outline", "tolerance": 0.5}]`. In the GUI:
Post-processing panel, "Smooth outline (SVG + DXF)". On a saved run:

```bash
toporia post results/mbb smooth_outline:method=chaikin,passes=3
```

## 📄 Candidates

| Post-processor | Reference | What it adds |
| :-- | :-- | :-- |
| 📄 Body-fitted re-analysis | Common practice; e.g. via FEniCS or Gmsh | Re-mesh the outline and analyse it again, free of the element grid |

## Writing one

Subclass `PostProcessor` and give it `name`, `label` and `params`; the constructor takes
each one as a keyword. Implement `process(result)`:

- it returns a dict of plain metrics (numbers, booleans or None);
- it writes files through `result.file(name)`.

`table_metrics` lists the metrics worth a column in a comparison (`()` for an exporter).
A post-processor can read:

- `result.density`, `result.problem`, `result.run`;
- `result.solid()`, the black-and-white design: the threshold's when one ran, else
  density ≥ 0.5;
- `result.geometry`, the explicit outlines when the design has them.

Then run `toporia check postprocessor:<name>`. It checks that:

- the metrics are plain values;
- every file it names exists and is not empty;
- the design it was given is unchanged;
- a second run gives the same numbers.

## References

- O. Sigmund, "Morphology-based black and white filters for topology optimization", *SMO* 33 (2007) 401–424.
- F. Wang, B. S. Lazarov, O. Sigmund, "On projection methods, convergence and robust formulations in topology optimization", *SMO* 43 (2011) 767–784.

## Research demonstrations

[Batch 4](../../../docs/research/batch-4.md) reuses saved fields/history for all eight post-processors, with separate figures and metric/file checks. [Gallery](../../../docs/research/evidence/batch4/index.html). Own connectivity/exports have no single originating paper; metrics/smoothing are not claimed as matched paper figures or manufacturing certificates.
