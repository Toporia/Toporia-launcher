# To do

One overview of every open task. It merges the earlier `To do.md`, the method-integration
plan [`toporia/plugins/TODO.md`](toporia/plugins/TODO.md) (which keeps its detailed tables)
and the open-code survey [`toporia/plugins/SURVEY.md`](toporia/plugins/SURVEY.md).

**Who added it.** 🧑 you · 🤖 Claude · 🅧 Codex. Taken from the commit that first introduced
each line (an AI co-author line in the commit means the agent wrote it); lines from the
handwritten "late session" note of 8 November 2026 are yours, and suggestions made while
planning it are Claude's.

Status: `[ ]` open · `[~]` in progress · `[x]` done.

---

## 1. Launch 0.3.0 (in this order)

From your late-session note (🧑, 8 November 2026), with the answers you gave on it.
Numbers are the note's own.

### Step 1: overview and test health

- [x] 🧑 Combine the To do, the methods to-do and the survey into one overview (this file).
- [x] 🤖 A GUI test assumed the optional pyMOTO is installed; it now ignores the "not installed" note.
- [x] 🤖 The full suite's process did not exit after passing (found at `372adc1`, 🤖). Not
      reproduced on 8 November 2026: with the opt-in exit tracer in `conftest.py`
      (`TOPORIA_EXIT_TRACE=<seconds>`) the run ended with no thread left and exited. Use the
      tracer if it comes back.
- [x] 🧑 Remove the Drone Arm presets: a project, not a benchmark. (Replaces 🤖's question
      about loading only the ring.) They are example projects in `examples/drone-arm/`; the
      checks and tests keep their geometry as the unlisted `Holes and Rings (test)`.

### Step 2: GUI quick wins

- [x] 🧑 4.5 Problem, Method, Run, Post and Export tabs always visible; clicking one with no
      project open makes a new project. Today Home is a dead end.
- [x] 🧑 22 Result folders are named `result_<projectname>` and sit next to the project file.
- [x] 🧑 23 Home has Benchmark and Function buttons, and lists recent projects.
- [x] 🧑 26 Rename a project from inside it.
- [x] 🧑 12 Remove the computation-notes bar at the bottom of the Method tab; if the method
      cannot run, Run shows a pop-up saying why.
- [x] 🧑 5 Export and import a problem directly from the Problem page.
- [x] 🧑 13 Selecting a part clears the parts that are incompatible with it. Every option stays
      selectable; those that would clear another part are greyed out.
- [x] 🧑 17 Pan and zoom in every view.
- [x] 🧑 21 A good preview on Export.

### Step 3: constraints and the method tree

- [x] 🧑 6 The material budget is a constraint like the others: it can be added or removed. A
      part that needs a volume fraction creates it; removing it sets that part back to blank.
- [x] 🧑 7 The Method tab shows the whole tree of components, with collapsible branches. The
      side has one "+" button that opens a pop-up of all functions and asks where to place
      one when there is more than one possible place.
- [x] 🧑 14 The top level of the graph is the optimisers and how they relate (opt 1, rules in
      between, opt 2), sequential or parallel; it cannot collapse further than that.
- [x] 🧑 19 The running mode (single, sweep, compare) is shown in the tree, just above the
      optimisation loop.

### Step 4: inspect and materials

- [x] 🧑 11 The post-processing tab is also the inspect tab: the result with all its data,
      fields and variables; for a sweep or comparison all runs, or a chosen few. Zoom and pan
      in any field, rotate in 3D. Applying a post-processor makes a modified copy of the field.
- [x] 🧑 20 View the analysis fields of the final geometry in colour: stress, strain,
      displacement, temperature.
- [x] 🧑 11 Materials defined in MPa, with presets: steels, aluminium, titanium, PE, PA (nylon),
      PLA, resin.

### Step 5: speed

- [x] 🧑 8 Faster startup and Method tab; a loading screen with a progress bar counting down
      the average start time.
- [x] 🧑 8 Running opens a pop-out window, so the main GUI stays responsive and usable.
- [x] 🧑 8 Use more of the hardware. 🤖 The finite-element solve is the bottleneck and runs on
      one core: an optional multithreaded solver (PARDISO) and parallel sweep and comparison
      runs. A GPU updater would not help, since the updater is not the slow part.
      Done: sweeps run in parallel processes. Still open: a multithreaded direct solver
      (PARDISO, optional) for single large runs.

### Step 6: appearance and help

- [x] 🧑 29 Two or three new styles, and a style maker.
- [x] 🧑 24 Each function has its own explainer text with an explanatory figure and its linked
      showcase, so not only in the benchmark tab.
- [x] 🧑 25 Home has a docs section: start guide, explanation of the structure, how to add things.

### Step 7: sync, 3D, compare, clean-up, release

- [x] 🧑 15 Constraints, physics and objective are editable in both the Problem and the Method
      tab, and stay in sync.
- [x] 🧑 18 A real 3D density view: the whole field as a cloud, not one averaged 2D view.
- [x] 🧑 28 Compare mode: choose the model once and change it, instead of a copy of every
      model for every physics.
- [x] 🧑 Clean file tree: compact READMEs, a tidy catalogue and docs; decide on `examples/` and
      `experiments/`; `results/` is not needed in the repository.
- [x] 🤖 Split into core, library and GUI (agreed 28 October 2026, 🤖; see section 4).
- [x] 🧑 Easy install on a new machine without Python: a zipped Windows folder (🧑 chose a zip
      over an installer; unsigned).
- [x] 🧑 Version 0.3.0.

## 2. After the launch

The framework redesign from the note (🧑). 🤖 suggested this order, because each builds on
the one before.

- [x] 🧑 4 Rethink the objective: list the variables in the design space, pick one or more to
      minimise or maximise, and choose how they combine. A variable can be a Python line of
      other variables, or a separate Python file for full control.
      🤖 Done 9 November 2026: the `combined` objective (weighted sum, min-max through the KS
      function, or a Python expression), and `peak_stress` as an objective. 🧑 chose no Python
      file for now.
- [x] 🧑 1 + 2 The problem space is a variable space: the Problem tab lists every variable and
      field (compliance, peak local stress, volume fraction, your own). 🤖 Scalars first;
      extra fields next to the density, or with a time axis, need the engine to carry more
      than one design field.
      🤖 Scalars done 9 November 2026: `scenario.variables` (measured or a formula), recorded
      every run, usable through the `variable` response; the Problem page lists built-in
      variables, your own, and the fields. Extra design fields and a time axis stay open
      (section 6, Wave 5).
- [x] 🧑 9 Physics and material law chosen in the Problem tab, several physics on one field,
      each with its own material law. 🤖 Combined through item 4 first; truly coupled physics
      is the "coupled solving" item below.
      🤖 Done 9 November 2026: the material law sits on the Problem page; "More physics on the
      same design" adds physics with their own law and solid/void property
      (`scenario.extra_physics`), measured by variables; preset MBB Beam (Stiffness and Heat).
- [ ] 🧑 3 Native truss representation (ground structure), and a function that converts a
      truss network back into a density field, which is then checked and optimised for peak
      stresses. Modules with transfer functions, for multi-level optimisation of flexure
      systems. 🤖 The truss, the conversion and the two-stage run first; transfer-function
      modules are research.
- [ ] 🧑 10 Each representation has its own view: a network with a value at each node and
      connection for a truss; the elements for element-based ones. Ask 🧑 where unclear.
- [ ] 🧑 16 Loads and constraints on the Problem page for all physics: springs, compliant ports,
      heat loss.
- [ ] 🤖 Point springs (compliant-mechanism ports) are kept on a custom copy but cannot be
      drawn or edited in the Problem editor yet; they need an object role. (Part of 16.)
- [ ] 🧑 27 A proper 3D editor.
- [ ] 🧑 A sleek website.

## 3. Human tasks

- [ ] 🧑 Get all the papers.
- [ ] 🧑 A contact list.
- [ ] 🧑 Expand function explanations and references with researcher input.

## 4. Split the repository into core, library and GUI

Agreed 28 October 2026 (🤖 written, 🧑 agreed); done before the launch, 8 November 2026 (🧑
chose before launch, and prefixed names to avoid clashes with other installed packages).

- [x] 🤖 `toporia_core/` (framework, registries, engine, checks, `api.py`, command line),
      `toporia_library/` (every function and the presets) and `toporia_gui/` (the desktop app).
- [x] 🤖 `toporia_core` imports neither of the others, `toporia_library` imports only the core;
      `tests/test_package_boundaries.py` enforces it for every import.
- [x] 🤖 The registries, `method_class` and the response checks live in the core; it finds the
      library's parts and presets, and the app, through entry points in `pyproject.toml`.
      `AssembledModel`, the filter pipeline and the comparison referee moved into the core.
- [x] 🤖 One `pyproject.toml`; PySide6 is the `gui` extra.
- [x] 🤖 Library PDFs in `docs/library/`; `results/` ignored.
- [ ] 🤖 Plotting (`engine/records.py`, the compare/sweep/sensitivity images) is imported only
      when used, but matplotlib is still a core dependency; making it optional is open.

## 5. Research and paper comparisons

- [ ] 🤖 top99neo Table 2 T1-T3: `python -m experiments.research_papers --case top99neo_t1`
      (and t2, t3), then `--publish-only` and drop them from `PENDING` in
      `tests/plugins/test_research_papers.py`. About four hours for the three.
- [ ] 🤖 Machining filter, single tool at 180 degrees: 4.72 times the reference against the
      paper's 4.11.
- [ ] 🤖 SiMPL (arXiv 2411.19421) MBB comparison in ratios; needs the 768 x 256 mesh.
- [~] 🧑 Interact with as many papers of the field as possible; a library of all the content in
      this field; well thought-through universal tests.
- [~] 🧑 Make interacting with Toporia much more general; programs that cannot return every
      iteration are not forced to.

## 6. Method integration backlog

Details, sources and licences in [`toporia/plugins/TODO.md`](toporia/plugins/TODO.md) (🤖);
waves 3 and 4 are complete. Open:

- [ ] 🤖 Wave 0: a systematic search for every open topology-optimisation code; correct the
      catalogue's 🔗/📄 markers. The verified survey so far is
      [`SURVEY.md`](toporia/plugins/SURVEY.md) (🤖).
- [ ] 🤖 Wave 1, Python packages: cyipopt (blocked: no Windows wheel for this Python), ParOpt,
      dl4to + SELTO datasets, JAX/AuTO, google-research neural-structural-optimization,
      ceviche, JAX-FEM, TOFLUX; ToPy, PyTopo3D and others as oracles; FEniTop, Firedrake and
      Meep after unstructured meshes.
- [ ] 🤖 Wave 2, MATLAB codes run unchanged as whole methods: one generic MATLAB Engine bridge,
      then top88, top99neo, top3d/top3D125, MMA/GCMMA, RBF, reaction-diffusion and Challis
      level sets, TOBS, MMC, GGP/GPTO, AM filter, buckling, non-linear, multi-material,
      PolyStress, topflow, 3-D stress. (Strict oracle checks are done; bridges are not.)
- [ ] 🤖 Wave 5, framework changes: several fields per element (DMO, fibres, multi-material);
      unstructured meshes; beam/truss elements and ground structures (see 🧑 item 3);
      multiscale, IGA, CutFEM; fluids, transient, acoustics, photonics; generative models.
- [ ] 🧑 Coupled solving and combination within optimisation iterations.
- [ ] 🧑 GUI for authoring new computational functions (document the extension interface first).
- [ ] 🧑 Export version control; more stress and price statistics.
- [ ] 🧑 Sweeps can change the optimiser.

## Done earlier

- [x] 🧑 GUI v0.2.1 scope ([docs/internal/gui-v0.2.1-scope.md](docs/internal/gui-v0.2.1-scope.md)), including the
      Basic / Sleek appearance selector.
- [x] 🤖 Every integrated computational method reachable in the GUI library (`full-gui`).
- [x] 🧑 A slicer-like GUI: steps one goes through before running, options on the side and top,
      explicit problem and solver, a network view of filters, post-processing and export.
- [x] 🧑 3D.
- [x] 🧑 Representations other than pixels: components (MMC/MMV), B-splines, neural fields,
      geometry projection. (Beams and truss are still open, item 3.)
