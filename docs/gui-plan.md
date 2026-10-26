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
- [ ] 7. Verify complete 2D open/edit/save/reopen/run/export workflow visually and
  with meaningful integration tests; document usage and remaining limitations.
- [ ] 8. General spatial regions and STL geometry adapter; independent 3D load/
  support/solid/void/domain assignments and conservative mesh validation.
- [ ] 9. 3D viewport and inspector with spatial primitives, imports, transforms,
  selection and camera navigation; reuse the shared project/object model.
- [ ] 10. Final cross-workspace verification, regression checks and handoff.

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

Next: milestone 7, visual verification of the complete 2D flow, documentation,
remaining input/viewport polish, and regression checks before 3D work.
