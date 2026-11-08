# Installing Toporia

From nothing to the GUI running, on Windows, macOS or Linux. Once it runs, continue with
[quickstart.md](quickstart.md).

## On Windows, without Python

1. Download `Toporia-0.3.0-windows.zip` from the release page.
2. Unzip it anywhere you can write to (your Documents folder, a USB stick). Unzipping into
   `C:\Program Files` also works, but keep your projects elsewhere.
3. Start `Toporia\Toporia.exe`. The program is not code-signed, so Windows SmartScreen may
   say the publisher is unknown: choose *More info → Run anyway*. The first start takes a
   little longer while Windows checks the files.

Nothing is installed or registered; to remove Toporia, delete the folder. To check that
everything works, run `Toporia.exe --smoke-test` from a terminal in that folder: it
builds the window and runs a small optimisation, and says *smoke test passed*.

Everything below is for running Toporia from its sources, on any system, and for
changing it.

## 1. What you need

| | |
| :-- | :-- |
| **Python 3.10 or newer** | [python.org/downloads](https://www.python.org/downloads/). On Windows, tick *Add python.exe to PATH* in the installer. Python **3.12 or 3.13** is the safest choice: every optional package has ready-made downloads for them (see [pyamg on very new Python](#pyamg-on-very-new-python)). |
| **Git** | [git-scm.com](https://git-scm.com/), to get the code. |

Check what you have:

```bash
python --version
git --version
```

## 2. Get the code

```bash
git clone https://github.com/Toporia/Toporia-launcher.git
cd Toporia-launcher
```

## 3. Make a virtual environment

A virtual environment (`.venv`) keeps Toporia's libraries apart from the rest of your
computer. It is already in `.gitignore`.

```bash
python -m venv .venv
```

Then activate it. You do this once per new terminal.

| System | Command |
| :-- | :-- |
| Windows, PowerShell | `.\.venv\Scripts\Activate.ps1` |
| Windows, cmd | `.venv\Scripts\activate.bat` |
| Windows, Git Bash | `source .venv/Scripts/activate` |
| macOS / Linux | `source .venv/bin/activate` |

Your prompt now starts with `(.venv)`. If PowerShell refuses to run the script, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.

## 4. Install Toporia and its libraries

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev,3d,gui3d]"
```

`-e` installs the code *editable*, so your changes to the files take effect without a
reinstall. The part in brackets picks the extras:

| Group | What it installs | What for |
| :-- | :-- | :-- |
| *(always)* | numpy, scipy, matplotlib, Pillow, PySide6 | the solver, plots, and the desktop GUI |
| `dev` | pytest, ruff | the test suite and the linter |
| `3d` | pyamg, scikit-image | the fast multigrid solver for large 3-D meshes, and the 3-D view |
| `gui3d` | pyvista, pyvistaqt, ezdxf | the interactive 3-D spatial editor in the GUI, and geometry import (DXF). 2-D works without it |
| `pymoto` | pyMOTO | `method="pymoto"` (sensitivities by backpropagation) |
| `nlopt` | NLopt | the `nlopt_mma`, `nlopt_ccsaq`, `nlopt_slsqp` and `nlopt_auglag` updaters |
| `mmapy` | mmapy *(GPL-3)* | the `mmapy_mma` and `mmapy_gcmma` updaters |
| `nullspace` | nullspace_optimizer *(GPL-3)* | the `nullspace` updater |

Combine any of them, for example `pip install -e ".[dev,3d,pymoto,nlopt]"`. The GPL-3
optimisers are never required. Toporia only imports them when you pick their updater.

## 5. Check it works

```bash
toporia
```

This opens the GUI. Pick **MBB Beam** and press **Run**.

```bash
toporia run "MBB Beam"
```

The same from the command line. It takes a few seconds and writes to `results/`.

```bash
pytest
```

The whole test suite, which takes several minutes.

`python main.py` also starts the GUI, if you prefer that to the `toporia` command.

## 6. VS Code

Open the folder, press `Ctrl+Shift+P`, choose **Python: Select Interpreter**, and pick the
one in `.venv`. New terminals inside VS Code then activate it automatically, and the Run
button and the test explorer use the right libraries.

## Troubleshooting

### `ModuleNotFoundError: No module named 'numpy'` (or PySide6, scipy, …)

The libraries are installed in a different Python than the one you are running. Usually
the virtual environment is not active. Activate it (step 3) and run again. To check which
Python is in use:

```bash
python -c "import sys; print(sys.executable)"
```

The path should end in `.venv\Scripts\python.exe` (Windows) or `.venv/bin/python`.

### `'toporia' is not recognized` / `command not found: toporia`

Same cause. Activate the virtual environment, or run `python main.py` instead.

### pyamg on very new Python

On a Python release newer than pyamg supports (for example Python 3.15), pip finds no
ready-made pyamg download and tries to compile it. That fails with an error like
`Could not find ...\vswhere.exe` or `metadata-generation-failed ... pyamg`.

pyamg is **optional**. Toporia uses the direct solver when it is missing, which handles
small and medium 3-D meshes fine. You have three choices:

1. **Skip pyamg.** Install everything else:
   ```bash
   python -m pip install -e ".[dev,gui3d]" scikit-image
   ```
2. **Use Python 3.12 or 3.13** for the virtual environment, where pyamg installs directly.
   On Windows, with the Python launcher:
   ```bash
   py install 3.13
   py -3.13 -m venv .venv
   ```
3. **Install a C++ compiler** so pip can build it: the
   [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
   with the *Desktop development with C++* workload on Windows, `xcode-select --install` on
   macOS, or `build-essential` on Linux.

The same applies to any optional package that fails to build on a very new Python.

### The GUI does not open on Linux

PySide6 needs a few system libraries for Qt. On Debian or Ubuntu:

```bash
sudo apt install libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0
```

## Building the Windows zip

On Windows, from the sources:

```bash
pip install -e ".[dev,3d,gui3d,build]"
python packaging/build_windows.py
```

It writes `dist/Toporia/` and `dist/Toporia-<version>-windows.zip`, and ends by running
the built program's `--smoke-test`. The optional packages installed when you build
(pyvista, scikit-image, …) go into the program; those that are not installed stay out.
