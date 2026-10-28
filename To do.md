# TO DO

- [] Make a slicer looking GUI for the mode definition and results
  - [] making it multiple windows one goes through before running
  - [] making like a slicer that the options are on the side and on the top
  - [] make the problem defention explicit
    - [ ]
  - [] make the solver explicit and add a network view of filters
  - [] post process and export
- [] 3D
- [] Other represenation except pixels in 2D or 3D. So like beams or like PBRM

- [] make the sweeps can change the optimizer
- [ ]  Make that each optimizer 

## Doing

- [ ] Make interact with as much papers of the field
  - [ ] Interact with one
  - [o] make a library of all the content in this field
  - [ ] Have a well tought through universal tests and do run the tests
  - [o] Make much more general how to interact with toporia. And for the programs that cannot return every run, dont force them.
## Split the repository into core, library and GUI (later in this batch)

Agreed 28 October 2026; not started. Target top level, next to `docs/`, `tests/`,
`experiments/` and `results/` (`main.py` stays):

- `toporia_core/`: only the glue every function uses, no functions. Problem
  description (`framework/problem`), part base classes (`framework/parts`),
  parameters, registry, external-optimiser adapter, the engine loop and run
  modes, the contract checks (`checks/`), `api.py` and the command line.
- `library/`: every function, today's `toporia/plugins/` (models, physics,
  updaters, filters, interpolations, representations, responses, schedules,
  postprocessors, methods) and the presets (`problems/`) with their research
  descriptions.
- `toporia_gui/`: only the visual program, today's `toporia/apps/gui/` plus the
  research HTML rendering. A run must work without it.

Rules:

- [ ] `toporia_core` never imports `library` or `toporia_gui`; `library` imports
      only `toporia_core`; `toporia_gui` imports both. Add a test that enforces it.
- [ ] Remove today's core-to-library imports by looking parts up through the
      registry: `engine/loop.py` (methods, responses), `engine/pipeline.py`
      (filters, interpolations, methods), `framework/parts/composition.py`
      (responses), `engine/modes/methods.py` (postprocessor measures, presets).
- [ ] Move plotting (`engine/records.py`, compare/sweep/sensitivity modes) out
      of the core so it needs only numpy and scipy.
- [ ] Decide the import name: `toporia_core` instead of today's `toporia`.
- [ ] One `pyproject.toml`; PySide6 becomes an optional GUI extra.
- [ ] Ignore `results/` and cache folders in git; move the library PDFs into `docs/`.
- [ ] Coordinate with the GUI workstream first: moving `apps/gui` clashes with its branch.
- [ ] Pure moves first, then the import changes, then docs; full suite after each commit.
