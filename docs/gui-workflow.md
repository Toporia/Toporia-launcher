# Project GUI v0.2.1

Launch `python main.py` from this checkout. Home has two entry cards:
**Benchmarks** (the sourced reference library) and **Functions** (the registry-backed
encyclopedia). Open/new/import actions remain nearby; benchmark previews load
only when their section is opened.
Use `python main.py --project path/to/project.top` to open a project directly.
The local `.venv` includes the optional spatial editor dependencies. On Windows,
use `.venv\Scripts\python.exe main.py` for the full 3D viewport. For a fresh
environment, install `pip install -e ".[dev,3d,gui3d]"` first.

## Files

- `.top`: readable JSON with the scenario, solver, output options, notes, study
  selections, a separate workflow configuration, and diagram/display state.
  It contains no computed result arrays. Earlier development snapshots with a
  workflow inside view state migrate without discarding the network.
- `.pro`: independently reusable physical problem and editor objects.
- A project's `results/` contains one new folder per run. `input.top` is the
  exact submitted configuration; `session.json` records its status. Finished
  single runs also contain `run.json` with numerical provenance and `design.npy`.
- Save/load never executes Python from configuration files. Unknown format
  versions and unknown top-level fields are rejected.

The File menu has new/open/save/save-as/import/export and benchmark-copy actions.
Standalone `.pro` definitions can also be supplied as the scenario to the CLI.
Unsaved changes prompt before replacing a project. View > Project notes opens
the associated notes pane. `examples/gui-cantilever/project.top` is an editable
2D example with explicit supports and a downward tip load.

## Problem

New blank problems start with only an unselected dimension. Choose dimension,
then representation, then the physical width/height (and depth in 3D) and element
size. The mesh counts appear before proceeding. Compatible physics choices are
then revealed, followed by material properties, objective and volume budget.
Nothing is preselected; enter each value and choose **Create design space**.
The normal editor and scalar controls appear afterward, with no automatic
supports or loads. Method starts with a compatible updater and the standard
density filter; review or change these in the Method step.

An unfinished setup can be saved as a `.top` project, including notes, and
reopened at the same point. Method/Runner/Post navigation, Run and independent
problem export are unavailable until the design space has been created. Existing
projects, imported problems and benchmark copies continue to open directly.

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
The current engine measures volume fraction against the rectangular bounding
grid, with excluded/outside cells empty; it does not renormalize the budget to
the imported shape's volume. This convention is shown in the domain inspector.
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

The top network contains the operating space, an optimization/composition
function, and a mandatory terminal export function. Click a container to make
its local network fill the workspace. **Parent** and **Workflow** navigate out;
the top and bottom contracts explain incoming data and expected output.
Optimization functions contain design representation, filters, physics calculation,
updater and convergence. Physics contains material law, physics, objective and
constraints. Select a computational leaf to open its actual parameter controls
in a contextual window; select it again or close the window to dismiss it.

The function library offers compatible insertions for the current network.
Double-click a library item or select it and press **Insert selected**. The
filter-chain network offers installed filters compatible with the problem's
dimension. Select a filter block to edit/reorder/remove filters. Schedules,
variants and study paths continue to refer to the same reordered filter.
Other method selectors show one representative current method for this release;
existing saved method selections remain readable. The initial problem editor
retains its available choices.

Dragging boxes changes their saved presentation, not computation. Arrowheads
follow the terminal connector direction after movement. Wheel zooms, dragging
empty space pans, and Fit/Reset layout restore a readable view. Computation notes
are collapsed by default. **?** opens contextual explanations; Home > Functions
contains plugin descriptions, parameters, references, placement and independent
infrastructure. See [function development](gui-function-development.md) to add
methods in code; GUI authoring is future work.

### Composition

At Workflow level, insert **Sequential stage** or **Parallel branch** to wrap
the existing function and add another optimization. Inside a composition,
insert optimizations or nested sequential/parallel functions. Each optimization
stores independent solver, objective, material budget and load-case settings.
Select/open that optimization before editing its local computational functions.
The operating domain, physical supports/load positions and mesh remain shared.

- Sequential connections include an explicit previous-volume transformation:
  density >= 0.5 becomes the next stage's allowed material domain. The next
  stage cannot reintroduce material outside it. Its volume budget is relative
  to that allowed volume. Initial restriction supports composed methods with
  element densities and no variants; incompatible stages are refused in preflight.
- Parallel branches receive the same input domain and finish independently.
  They are scheduled consecutively to limit peak memory, then combined. They
  do not exchange data every iteration. Select union, intersection, or difference
  in the composition's library. Difference means first branch minus all others;
  all Boolean operations cut completed densities at 0.5 on the shared mesh.
- Every pipeline has terminal export. Boolean results have no single evaluated
  physical objective or proven feasibility; individual stage provenance remains
  available. Coupled physics and combination during iterations are future work.

Networks and the selected optimization are saved in the `.top` document. Each
workflow stage writes its exact design, numerical provenance and history in a
separate subfolder. Restricted stages also save `allowed_domain.npy`.

## Runner, Post-process and Export

**Run appears only in step 3 (Runner).** It first saves the project, validates
inputs, and launches an independent
headless process from the immutable snapshot. Inputs are frozen until completion;
the interface, plots and console remain responsive. Stop requests interruption
after the current numerical iteration; it cannot interrupt a native sparse solve
mid-operation. Stopped/failed runs are distinguished from finished designs.

Select a saved session in Runner to inspect it. A session left running by power
loss is shown as unfinished. Starting another run always creates a fresh folder.
The application can reopen its saved inputs; it does not yet resume optimizer
internal state from the middle of an iteration.

**Display options** controls live updates (on/off), update interval (default 1),
visibility of volume fraction/iteration/objective values, and optional graphs.
The objective is named explicitly. Its graph is on by default; the volume graph
and iteration progress bar are off by default. Iteration progress uses the actual
maximum iteration count rather than pretending early convergence reached that
limit. Burst updates are coalesced into Qt frames. Volume fraction is measured
against the original rectangular mesh, as in the existing numerical engine.

**Post-process (step 4)** initially offers one manually executed operation:
density < 0.5 becomes 0, density >= 0.5 becomes 1. Executing it refreshes the figure
immediately and saves `post/current_design.npy`. Objective values/curves are
explicitly labeled as source-run values that have not been re-evaluated.

**Export (step 5)** writes the current processed result (or the original result
when no operation was applied) to a chosen folder. STL, 2D SVG/DXF and NumPy
density exports are available. The format exporters put files under the chosen
folder's `post/` subfolder; NumPy writes `design.npy` directly. Export preserves
the displayed Boolean geometry even if it removed a region fixed in an input.
Export version control is future work. Legacy saved automatic postprocessor lists
remain compatible but are not the manual post-processing UI.

Result ownership resets on project changes. Regional
definitions cannot use the legacy Compare Load Cases editor yet: its shared
magnitude/angle controls do not describe independent regional vectors. Other
existing compatible studies remain available.

## Development handoff

`docs/gui-v0.2.1-scope.md` is the current implementation checklist; `gui-plan.md`
records the earlier GUI work. v0.2.1 lives on `gui-v0.2.1`. No integration or
launcher checkout is modified, and numerical golden baselines are not regenerated.
View > Appearance selects **Basic** or **Sleek monochrome**, and remembers the
choice for the next launch. Basic uses plain Qt controls. Sleek uses black
surfaces, white text/icons and thin borders, including network/editor backgrounds
and plot surrounds. Physical support/load colors and scientific result data keep
their meaning. Switching appearance preserves configuration, live result data,
network positions and unapplied editor inputs. It uses ordinary styling with no
blur, animated effects or custom shader pipeline.
For density images, solid is dark in Basic and white in Sleek so it remains
visible against the surrounding background; the density values do not change.
