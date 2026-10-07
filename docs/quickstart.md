# Quick start: changing Toporia

From a fresh checkout to your own part running in the GUI, in about fifteen minutes.
For every kind of part in detail, see [writing-plugins.md](writing-plugins.md). For how the
code fits together, see [toporia/README.md](../toporia/README.md).

## 1. Set up

```bash
pip install -e ".[dev,3d]"
```

`dev` brings the test tools. `3d` brings the fast 3-D solver (pyamg) and the 3-D view
(scikit-image). Add `pymoto` for the pyMOTO models and optimisers. Then check that
everything works:

```bash
toporia
```

This opens the GUI. Pick **MBB Beam** and press **Run**.

```bash
toporia run "Cantilever 3D"
```

The same from the command line, in 3-D. Results go to `results/`.

```bash
pytest
```

The whole test suite. It takes several minutes; `pytest tests/plugins -k oc` runs a part of it.

## 2. Where your change goes

Almost every change from a paper is **one new file in one folder of
[`toporia/plugins/`](../toporia/plugins/README.md)**. A file there is found automatically:
no registration, no list to edit.

| A paper that changes… | Is a… | In folder |
| :-- | :-- | :-- |
| how the design moves each iteration | updater | `updaters/` |
| what the design variables are | representation | `representations/` |
| smoothing, projection, a fabrication rule | filter | `filters/` |
| how density becomes stiffness | interpolation | `interpolations/` |
| what is minimised or limited | response | `responses/` |
| a parameter during the run (continuation) | schedule | `schedules/` |
| what is made of the result (checks, exports) | post-processor | `postprocessors/` |
| the physics or the element | physics engine + a 3-line model | `physics/`, `models/` |
| the whole method at once | whole method | `methods/` |
| a benchmark case | problem preset | `problems/` |

Each folder's README lists what is implemented and what exists elsewhere, with references.

## 3. Your first part, step by step

The example is a post-processor that reports how much material the finished design uses,
in cubic millimetres. It's a small, real part, and it's run by the test suite, so it works
as written.

**Step 1: write the file.** Save this as `toporia/plugins/postprocessors/material_volume.py`:

```python
# example: postprocessor
import numpy as np

from toporia.api import Param, PostProcessor


class MaterialVolume(PostProcessor):
    """The material in the black-and-white design, in mm³ (a 2-D design at a given thickness)."""

    name = "quickstart_material_volume"
    label = "Material volume (quick start example)"
    dims = (2, 3)
    params = (Param("thickness", 1.0, "Thickness", "Depth of a 2-D design.", min=0.01, max=1000.0),)

    def __init__(self, thickness=1.0):
        self.thickness = float(thickness)

    def process(self, result):
        problem = result.problem
        element = problem.dx * problem.dy * (problem.dz if problem.dims == 3 else self.thickness)
        return {"volume_mm3": float(np.sum(result.solid()) * element)}
```

Three things make it a Toporia part:

- a **`name`** (how runs refer to it) and a **`label`** (what menus show);
- its tunable values declared as **`params`**, each a constructor argument;
- the one method its kind requires, here `process`.

`dims = (2, 3)` says it works in 2-D and 3-D.

**Step 2: see it found.**

```bash
toporia list
```

It appears under *Post-processors*. In the GUI it is now in the **Post-processing** panel,
with its *Thickness* field generated from the `Param`.

**Step 3: check it.**

```bash
toporia check postprocessor:quickstart_material_volume
```

The conformance check runs it on a real design and confirms that:

- its numbers are plain values;
- every file it names exists;
- the design it was given is left unchanged;
- a second run gives the same answer.

Every kind of part has such a check. For an updater it includes a benchmark against
optimality criteria; for a filter or response it compares the gradients with finite
differences.

**Step 4: use it.**

```bash
toporia run "MBB Beam" --set 'postprocess=[{"type": "quickstart_material_volume"}]'
```

Its number is printed, and written to `results/.../run.json`. In **Compare Methods** it
becomes a column, the same for every method.

**Step 5: finish.** Add a row to the folder's README (`✅`, with a link to the file), and a
test if the part has behaviour worth pinning. `tests/` mirrors the package.

## 4. Before you commit

```bash
ruff check toporia tests
```

Must print nothing.

```bash
pytest
```

All tests pass, including the golden baselines (see below).

`tests/golden/` pins eight runs bit for bit. If one fails:

- **you didn't mean to change results:** that's a regression; fix it;
- **you did:** say so in the commit and regenerate that case:

```bash
python tests/golden/regenerate_baselines.py mbb_oc
```

## 5. Rules worth knowing

- **Use `problem.shape`, not `nely, nelx`.** A design is `(nely, nelx)` in 2-D and
  `(nelz, nely, nelx)` in 3-D. A part that handles only one says so with `dims`. A part
  used where it doesn't fit is refused before the run, with the parts that would work.
- **A response's gradient is with respect to the physical density.** The model carries it
  back through the filters and the representation.
- **Constraints are normalised so that `value ≤ 0` means satisfied.**
- **Optional packages are imported inside your methods, and declared:**
  `dependencies = ("nlopt",)`. Where the package is missing, the GUI greys the part out with
  the install command, instead of failing part-way through a run.
- **`framework/` imports nothing from the rest of Toporia.** To change an interface, add an
  optional method with a default rather than change an existing one; every plugin is
  written against it.
- **Plugins in your own package** need no change here at all. Import from `toporia.api` and
  declare an entry point; see
  [writing-plugins.md](writing-plugins.md#packaging-outside-this-repository).

## 6. Where to look next

| To understand… | Read |
| :-- | :-- |
| the layers and the life of a run | [toporia/README.md](../toporia/README.md) |
| every interface a part implements | [toporia/framework/README.md](../toporia/framework/README.md) |
| the loop, the stopping rule, what a run writes | [toporia/engine/README.md](../toporia/engine/README.md) |
| the GUI and the command line | [toporia/apps/README.md](../toporia/apps/README.md) |
| every kind of part, with a worked example | [writing-plugins.md](writing-plugins.md) |
| what exists in the field, and what is here | [toporia/plugins/README.md](../toporia/plugins/README.md) |
