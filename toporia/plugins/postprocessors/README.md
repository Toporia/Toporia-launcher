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

**In 3-D**: threshold, connectivity (pieces share a face), feature size and the STL solid work;
the images show the design as seen through its depth. The SVG and DXF outlines are 2-D only.

**Status: 6 in Toporia · 0 with open code · 3 paper only**

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
| ✅ SVG outline | [`export_svg.py`](export_svg.py) | `export_svg` | The outline in mm, for figures |
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

## 📄 Candidates

| Post-processor | Reference | What it adds |
| :-- | :-- | :-- |
| 📄 Smoothed outlines | Subedi et al., *J. Comput. Inf. Sci. Eng.* 2020 (a review of geometric post-processing) | Outlines smoothed or fitted with splines, instead of contours of the element field |
| 📄 Body-fitted re-analysis | Common practice; e.g. via FEniCS or Gmsh | Re-mesh the outline and analyse it again, free of the element grid |
| 📄 Measure of non-discreteness over the run | Sigmund, *SMO* 33 (2007) | Grey level plotted over the iterations rather than at the end only |

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
