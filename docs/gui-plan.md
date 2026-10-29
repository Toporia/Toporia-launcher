# GUI implementation plan and handoff

Work only in `toporia-gui`, branch `GUI`. Do not edit the integration or launcher
checkouts, merge branches, push, or change numerical golden baselines.

Source: the user's nine handwritten pages, T GUI.pdf, and chat clarifications.
The user authorized implementation on 26 October 2026. Work linearly; each
completed step is a separate commit and updates this file. An unchecked item is
not complete. Resume from the first unchecked step after reading git status.

## Accepted design

- Home opens/creates projects and presents illustrated, sourced benchmarks.
- Configuration is readable text, independent of results. Problem definitions
  can be imported/exported independently. Projects contain notes and assets.
- Four persistent steps: Problem, Method, Runner, Post & Export. Each has its
  own main workspace. The Problem editor starts with benchmark / blank / import.
- Benchmarks are read-only; copy one to make a custom definition.
- Problem: dimension, representation and resolution are separate nearby controls;
  geometry and scalar settings are separate; an object list and inspector share
  selection with the viewport. Points, lines and regions receive support/load/
  solid/void roles. Coordinates remain physical, independent of mesh resolution.
- Method: the supported pipeline is fixed; blocks are selectable/movable, with
  editable parameters. Filters can be added/reordered within the filter block.
  Arbitrary executable graphs are future work.
- First complete 2D, then full 3D and STL assignments. H8 elements are genuinely
  3D; the legacy extruded definition must not be confused with a spatial editor.
- Imported STL can define a domain, solid/void region, support or load region.
  Initial regional loads are a total force distributed across selected nodes.
- Unsupported physics/representation combinations must be explained. Blank
  custom problems must not acquire the legacy solver's implicit supports/loads.

## Linear milestones

- [x] 0. Inspect repository, record requirements and checkpoints (this commit).
- [x] 1. Versioned project document and atomic save/load; separate problem files,
  notes, UI state and run output; serialization tests.
- [x] 2. Home/library and file actions; benchmark cards/previews, descriptions,
  immutable originals, editable copies, notes and unsaved-change handling.
- [x] 3. Distinct step workspaces; interactive Method diagram and filter ordering;
  preserve generated plugin controls and existing analysis modes.
- [x] 4. Interactive 2D geometry editor: selection/list/inspector, numeric and
  graphical creation, transforms, domain/material settings, undo/redo and navigation.
- [x] 5. Compile custom 2D objects to solver inputs; independent regional loads,
  explicit supports, full/void regions, compatibility and preflight checks.
- [x] 6. Runner/results: prevent setup edits during execution, safe stop/error
  handling, project-specific output, fresh run directories and result provenance.
- [x] 7. Verify complete 2D open/edit/save/reopen/run/export workflow visually and
  with meaningful integration tests; document usage and remaining limitations.
- [x] 8. General spatial regions and STL geometry adapter; independent 3D load/
  support/solid/void/domain assignments and conservative mesh validation.
- [x] 9. 3D viewport and inspector with spatial primitives, imports, transforms,
  selection and camera navigation; reuse the shared project/object model.
- [x] 10. Final cross-workspace verification, regression checks and handoff.
- [x] 11. Progressive blank-project setup: explicit choices, resumable drafts,
  compatible initial methods, run/export guards and focused regression checks.

## Current checkpoint

Initial HEAD: ef0ad73. Working tree was clean on branch GUI.
No AGENTS.md was found in the GUI checkout or its workspace parent.
Python: C:/Users/johan/AppData/Local/Python/pythoncore-3.14-64/python.exe
PySide6 6.11.1, pytest 9.1.1, ruff 0.16.6 are installed.

The current GUI generates plugin parameter forms; the window builds a Run from
Scenario + Solver + Output. Scenario/Solver already have strict JSON helpers.
The numerical engine has pinned baselines. Preserve default serialized scenario
shape for legacy runs when adding custom geometry support.

Milestone 1 complete: project.py supports strict versioned .top and .pro JSON,
legacy scenario imports, portable output settings, notes/study/view state and
atomic writes. Validation: 18 project tests passed; ruff passed.
Pytest needs --basetemp=results/<unique-test-name> in this sandbox because its
system temporary-directory numbering fails. This is an environment issue.

Milestone 2 complete: Home has sourced illustrated benchmark cards and search.
File menu supports new/open/save/save-as/import/export/copy, and View opens notes.
Benchmarks protect physical controls. Save/discard/cancel protects replacements.
Study settings (including comparison methods/load cases) round-trip with notes.
Result ownership resets on project changes. Validation: 176 existing GUI/project
checks and 4 new lifecycle tests passed; GUI ruff checks passed.

Milestone 3 complete: Problem/Method/Runner/Post each has a main workspace.
Method uses a zoom/pan/select/drag scene; node selection borrows the real parameter
controls into its inspector and returns them when leaving. The graph's topology
is fixed. Filter rows have up/down controls; schedules/variants/study paths follow
reordered filters. Diagram positions are project presentation state, not solver
inputs. Validation: 180 regression checks plus 6 project/workspace tests passed.
Ruff passed. No optimisation engine changes.

Milestone 4 complete: physical-coordinate 2D editor with point/line/rectangle/
circle tools, object list and inspector, role assignment, numeric coordinates,
translation/rotation/scale, duplication, deletion and definition-level undo/redo.
Benchmark geometry is visible and immutable; copying produces explicit editable
objects. Domain dimensions/material edits preserve object coordinates. Scene
objects persist in project/problem files. Validation: 176 GUI/editor/lifecycle
checks passed; ruff passed after correcting QGraphicsScene ownership.

Milestone 5 complete: explicit regions are compiled in framework/problem/regions.py.
Legacy presets bypass the adapter and retain their historical serialization and
numerical baselines. Custom 2D objects produce support, solid/void/domain masks
and independent per-case total force vectors in Q4 and pyMOTO. Level-set auxiliary
meshes now preserve explicit definitions. Validation catches missing supports/
loads, residual rigid-body modes, unmeshed regions, excluded loads, material
conflicts and budgets. Definitions remain in physical coordinates. Imported
object structure is checked before it reaches graphics widgets.
Validation: 378 framework/application tests passed; 29 regional/golden checks
passed after active-material validation; ruff passed. Golden files unchanged.

Milestone 6 complete: Qt launches a headless worker process using immutable
input.top snapshots in unique per-project run folders. Setup edits are frozen,
plots/logs remain responsive, Stop is cooperative at an iteration boundary.
Each session records finished/stopped/error/interrupted state. Results/history
are owned by the active project; new runs do not overwrite old runs, and only
finished single results enable post-processing. All legacy study modes dispatch
from saved plain values. Regional load vectors are edited per object; legacy
Compare Load Cases is explicitly blocked for regional definitions because its
shared-vector controls would have no physical effect.
Validation: 202 application checks passed; 11 worker/lifecycle tests passed,
including real headless subprocesses and two actual QProcess runs. Ruff passed.

Milestone 7 complete: visually inspected Home, benchmark Problem, Method and a
completed custom 2D run in the native app. Fixed PySide text-item ownership,
physical Fit bounds and force arrows; added approximate target element count,
keyboard undo/redo/delete, direct --project launch and benchmark-copy affordance.
The example examples/gui-cantilever/project.top is editable configuration only.
User instructions are in docs/gui-workflow.md. Final 2D checks: 177 GUI/editor
checks plus 12 worker/lifecycle/mesh checks passed, including repeated asynchronous
runs and post-run SVG export. Ruff passed. Results live under ignored results/.

Milestone 8 complete: genuinely spatial point/line/face/box/sphere/cylinder
sampling, Euler transforms, regional H8 vectors, and STL volume/surface sampling.
Legacy extruded copies retain through-depth geometry and trapezoidal layer load
shares. STL triangles are embedded as readable vertices/faces for portable .pro
and .top documents, including support and load roles. Surface patches are allowed
for supports/loads; material/domain roles require closed manifold volumes. Added
geometry-only DXF profile importer for straight closed XY polylines/circles.
Optional gui3d dependencies installed only into the local .venv; numpy/matplotlib/
Pillow aligned to the existing verified versions. Validation: 35 regional/spatial/
golden checks passed, including an actual H8 optimization and STL portability.

Milestone 9 complete: optional lazy VTK/Qt viewport with full XYZ inspector,
primitive creation on an adjustable XY plane, object picking/list selection,
translation/rotation gizmos, numeric scaling, camera navigation/orientation widget,
STL role/sampling assignment, and DXF import. Shares object definitions, undo,
serialization and masks with 2D. Added true spatial example. Native Windows
rendering and list/XYZ selection verified. Fixed renderer initialization reentry
and responsive toolbar/axis labels. Offscreen form tests avoid requiring a GPU.
Validation: 178 existing GUI/editor checks passed; 16 spatial-editor/headless-
worker checks passed including H8 subprocess output. Ruff passed.

Milestone 10 review: removed duplicated embedded geometry from documents while
keeping editor objects authoritative for headless execution; validated saved
camera/diagram state; made result-session paths relative; improved failed-worker
cleanup and final logging; restored graph refresh on numeric schedule edits;
made legacy extrusion depth editable; rejected out-of-domain point assignments.
Added regression coverage and updated the existing unattended window-close test
to discard its intentional project edit. The production unsaved-change prompt
remains active. Documented the bounding-grid volume budget convention and .pro
CLI import. User's open Untitled window was left alone during final review.

Milestone 10 complete: full regression run passed on 27 October 2026:
630 passed, 1 skipped, 28 dependency warnings in 17m19s. The diagnostic timer
reported a long-running numerical test; the suite continued and exited zero.
Report: ignored results/pytest-full-recorded.xml and pytest-full-recorded.log.
Ruff, compileall and git diff --check pass. Numerical golden files unchanged.
All milestones are complete in separate linear commits on GUI; no merge/push
was performed. Integration and launcher working trees were not edited.

Launch for review from this checkout: `.venv\Scripts\python.exe main.py`.
Usage and limitations: docs/gui-workflow.md. Start with either example project
under examples/gui-cantilever or examples/gui-spatial. Future changes should use
new milestones/commits rather than rewriting this completed checkpoint sequence.

For tests in this Windows sandbox, use a workspace-local TEMP as well as pytest's
basetemp. The sandbox denies cleanup of some default temporary directories:

```powershell
New-Item -ItemType Directory -Path results/test-temp -Force | Out-Null
$env:TEMP = Join-Path (Get-Location) 'results\test-temp'
$env:TMP = $env:TEMP
& .venv/Scripts/python.exe -m pytest --basetemp=results/pytest-unique-name
```

Milestone 11 complete: new blank projects show only an unselected dimension,
then progressively reveal compatible representations, physical sizes/resolution,
physics/material and objective/budget. No creation field is preselected. Creating
the domain opens the normal editor without invented supports/loads. The initial
updater is compatible with the representation (OC for densities, MMA for MMC);
method settings remain editable. Partial setup lives in project view metadata,
can be saved/reopened with notes, and is validated before replacing a document.
Method/Runner/Post navigation and run/problem export are gated until creation;
the headless worker also rejects incomplete drafts. Existing projects and imports
open directly. Setup ranges match the editor to avoid silent clamping.
Validation: 251 application/plugin regression checks passed; 49 focused checks
passed after range alignment, including a real worker rejection. Ruff, compileall
and diff whitespace checks pass. Reviewed initial and completed setup renders
offscreen with an explicitly loaded Windows font. No live user window disturbed.
Only the GUI checkout was edited. Next work starts as a new milestone.
