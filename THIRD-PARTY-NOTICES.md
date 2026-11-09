# Third-party software and licences

Toporia itself is licensed under the Apache License 2.0 ([LICENSE](LICENSE)). It uses other
open-source packages. This page says which ones come with Toporia, under which licence,
and which ones are deliberately left out.

## The licence issue, in short

Apache-2.0 is permissive: anyone may use, change, sell or close-source Toporia, as long as
the licence notice is kept. GPL-3 is copyleft: whoever passes a program on that contains
GPL-3 code must pass it on under GPL-3, with its full source.

Two optional optimisers are GPL-3: **mmapy** (the `mmapy_mma` and `mmapy_gcmma` updaters)
and **nullspace_optimizer** (the `nullspace` updater). Toporia therefore:

- **never installs them by default:** they are extras, installed only when you ask:
  `pip install "toporia[mmapy]"` or `pip install "toporia[nullspace]"`;
- **never bundles them:** the Windows program (`Toporia-<version>-windows.zip`) does not
  contain them, even when they are installed on the build machine. The build script
  (`packaging/build_windows.py`) excludes them and checks that they are absent;
- **imports them only when their updater runs.** Without them, those updaters are greyed out
  in the app with the install command, and every other part works.

If you install a GPL-3 optimiser yourself and use it, that is your own use and is allowed.
If you redistribute a program that contains one, that program must be distributed under
GPL-3. Toporia's own MMA (`mma`) and pyMOTO's MMA and GCMMA (`pymoto_mma`, `pymoto_gcmma`)
cover the same methods without that obligation.

The null-space optimiser currently cannot be installed on Python 3.15: its dependencies
cvxopt, osqp and piqp have no wheels for it yet.

## Installed with Toporia and contained in the Windows program

| Package | Used for | Licence |
| :-- | :-- | :-- |
| NumPy | arrays everywhere | BSD-3-Clause |
| SciPy | sparse solvers, optimisers | BSD-3-Clause |
| Matplotlib | images, plots in the app | Matplotlib licence (PSF-style) |
| Pillow | image files | MIT-CMU (HPND) |
| pyMOTO | `pymoto` model, `pymoto_mma`, `pymoto_gcmma` | MIT |
| SymPy, mpmath | required by pyMOTO | BSD-3-Clause |
| PySide6 / Qt | the desktop app | LGPL-3.0, used as separate, replaceable libraries |
| PyVista, VTK | the 3-D editor and viewer | MIT, BSD-3-Clause |
| ezdxf | DXF import and export | MIT |
| scikit-image | the 3-D surface view | BSD-3-Clause |
| PyAMG | multigrid solver for large 3-D meshes (when installed at build time) | MIT |
| PyInstaller bootloader | starts the Windows program | GPL-2.0 with an exception that allows non-free programs |

The LGPL parts (Qt through PySide6) are shipped as separate library files
in the program folder, so they can be replaced, as the LGPL requires. Their licence texts
are in the program folder next to each library.

## NLopt: installed where it works

NLopt (the `nlopt_*` updaters; MIT, with parts of its C library under LGPL-2.1) is a default
dependency only where pip finds a build that loads. The newest NLopt on PyPI (2.6.2) is
compiled for Python 3.8 and older: on newer Pythons it installs but cannot load, so Toporia
checks its compiled core and greys the updaters out. The Windows program, built on Python
3.15, therefore does not contain NLopt. Where a working build exists (`conda install -c
conda-forge nlopt`, or an older Python), `pip install "toporia[nlopt]"` adds it.

## Optional, never contained in the Windows program

| Package | Used for | Licence | Install |
| :-- | :-- | :-- | :-- |
| mmapy | `mmapy_mma`, `mmapy_gcmma` | GPL-3.0 | `pip install "toporia[mmapy]"` |
| nullspace_optimizer | `nullspace` | GPL-3.0 | `pip install "toporia[nullspace]"` |
