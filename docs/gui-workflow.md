# Project GUI

Launch `python main.py` from this checkout. Home offers a sourced benchmark
library, a blank physical definition, and project/problem import.
Use `python main.py --project path/to/project.top` to open a project directly.
The local `.venv` includes the optional spatial editor dependencies. On Windows,
use `.venv\Scripts\python.exe main.py` for the full 3D viewport. For a fresh
environment, install `pip install -e ".[dev,3d,gui3d]"` first.

## Files

- `.top`: readable JSON with the scenario, solver, output options, notes, study
  selections and diagram arrangement. It contains no computed result arrays.
- `.pro`: independently reusable physical problem and editor objects.
- A project's `results/` contains one new folder per run. `input.top` is the
  exact submitted configuration; `session.json` records its status. Finished
  single runs also contain `run.json` with numerical provenance and `design.npy`.
- Save/load never executes Python from configuration files. Unknown format
  versions and unknown top-level fields are rejected.

The File menu has new/open/save/save-as/import/export and benchmark-copy actions.
Unsaved changes prompt before replacing a project. View > Project notes opens
the associated notes pane. `examples/gui-cantilever/project.top` is an editable
2D example with explicit supports and a downward tip load.

## Problem

Reference problems are immutable; use **Copy to custom** to make an editable
definition. Changing a solver does not change the original benchmark's physical
problem. A blank custom definition has no automatic supports or loads.

Dimension, representation and resolution are separate controls. Resolution can
be entered as elements/mm, element size or an approximate target element count;
the actual rounded mesh counts are displayed. Domain size and physical material
are in the inspector. SIMP/RAMP interpolation is in Method.

Select Point and click once; Line and Rectangle use two clicks; Circle places
an initial circle whose diameter can be entered exactly. Coordinates are mm from
the bottom-left domain origin. Select in the canvas or object list, edit the
inspector, then **Apply object changes**. Drag to translate, or enter position,
rotation and scale numerically. Circle position is its centre; rectangle position
is its lower-left corner; line size is the signed endpoint offset. Polygon copies
retain their vertices. Select or Pan changes the navigation mode; wheel zooms;
Fit shows the domain and all objects. Undo/Redo applies to physical edits; Delete
removes a selected object and can be undone.

Objects have roles: support, load, forced solid, excluded material, or design
domain. Multiple domain objects form a union. Solid and void must not overlap.
Supports select displacement axes. Each load object owns a **total force vector**
and a load-case number; the vector is divided evenly across its selected mesh
nodes, so mesh refinement does not multiply the load. Load Cases controls the
number and weights of cases. Magnitude/angle fields are only used by legacy
presets. Every custom case must have a load.

Preflight reports insufficient supports (a rigid-body rank test), invalid regions,
zero-cell meshes, missing loads and material conflicts. Regions that sample no
nodes/elements require a finer mesh or larger region. These checks do not prove
stability for every disconnected topology or future physics model.

## Spatial objects and geometry imports

3D uses H8 elements with XYZ coordinates. A spatial point is one physical point;
it is not a line repeated through the depth. A copied legacy 3D benchmark retains
its explicitly marked extrusion and original through-depth load shares.

The 3D viewport uses the same object list, inspector, undo and files as 2D. Select
Box, Sphere or Cylinder (or a point/line/surface tool), then click the XY placement
plane. Change Placement plane Z to create at another elevation. Enter precise XYZ,
three-axis rotations and sizes in the inspector. A box with one zero dimension
can define a support/load face. Spheres use diameters and a centre; cylinders use
XY diameters and a base Z with a height. Select an object in the list or viewport
to show translation/rotation handles. Uniform scaling is entered in the inspector.
Pan mode, Shift+drag, wheel zoom, Fit, standard camera buttons and the interactive
orientation widget provide navigation. Camera arrangement is project view state.

Import geometry accepts STL in 3D and DXF in 2D. STL triangles are embedded in the
readable project/problem file, so the source STL can be moved without breaking the
project. STL size fields are scale factors. Assign domain, support, load, solid
or void in Role. Closed volume sampling requires a closed manifold mesh; surface
proximity sampling accepts open support/load patches. Surface selection uses a
mesh-dependent distance tolerance, so inspect/refine the mesh for small details.
Loads are total vectors shared across selected nodes, not pressure/traction.

DXF import currently supports closed straight XY polylines and XY circles.
Unsupported entities are reported rather than partly discarded. Imported profiles
can be moved, rotated, scaled and assigned roles. Native CAD booleans, surface
repair, arbitrary unstructured meshing and graph rewiring remain future work.

`examples/gui-spatial/project.top` is a true spatial H8 example. STL regions need
the optional geometry libraries even for a headless worker; primitive spatial
regions can be solved without a renderer.

## Method

The main canvas displays the supported optimisation pipeline. Select a block to
show its actual generated parameter controls on the left. Dragging boxes changes
the diagram arrangement, not computation. Wheel zooms, dragging empty space pans,
and Fit/Reset layout restore a readable view.

Filters execute in their listed order. Use ↑/↓ in Filters to reorder them;
schedules, variants and study paths continue to refer to the same filter. General
graph rewiring is intentionally reserved for a later implementation.

## Runner and Post & Export

Run first saves the project, validates inputs, and launches an independent
headless process from the immutable snapshot. Inputs are frozen until completion;
the interface, plots and console remain responsive. Stop requests interruption
after the current numerical iteration; it cannot interrupt a native sparse solve
mid-operation. Stopped/failed runs are distinguished from finished designs.

Select a saved session in Runner to inspect it. A session left running by power
loss is shown as unfinished. Starting another run always creates a fresh folder.
The application can reopen its saved inputs; it does not yet resume optimizer
internal state from the middle of an iteration.

Post & Export applies the selected post-processors to a completed single result,
without reoptimising. Result ownership resets on project changes. Regional
definitions cannot use the legacy Compare Load Cases editor yet: its shared
magnitude/angle controls do not describe independent regional vectors. Other
existing compatible studies remain available.

## Development handoff

`docs/gui-plan.md` is the linear implementation checklist and validation log.
Each completed milestone has its own commit on GUI. No integration or launcher
checkout is modified, and numerical golden baselines are not regenerated.
