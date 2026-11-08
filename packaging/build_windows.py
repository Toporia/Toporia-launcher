"""Build the Windows program as a zipped folder: dist/Toporia-<version>-windows.zip.

    pip install -e ".[dev,3d,gui3d,build]"
    python packaging/build_windows.py

Unzipped, Toporia/Toporia.exe runs without Python.  The folder holds the program, its
libraries, the documentation and the example projects (help, Docs and the showcase
figures read them).  The build ends with Toporia.exe --smoke-test, which builds the
window and runs a small optimisation inside the bundle.
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from toporia_core import __version__  # noqa: E402

DIST, BUILD = ROOT / "dist", ROOT / "build"
NAME = "Toporia"


def pyinstaller():
    sep = ";"                         # PyInstaller's source;destination separator on Windows
    data = [("docs", "docs"), ("examples", "examples"), ("README.md", "."), ("LICENSE", "."),
            ("CITATION.cff", ".")]
    command = [sys.executable, "-m", "PyInstaller", str(ROOT / "main.py"), "--name", NAME,
               "--noconfirm", "--clean", "--windowed", "--distpath", str(DIST), "--workpath", str(BUILD),
               "--specpath", str(BUILD),
               # Parts are found by scanning their packages, so every module and data file goes in;
               # the core finds the library and the app through entry points: copy the metadata.
               "--collect-submodules", "toporia_core", "--collect-data", "toporia_core",
               "--collect-submodules", "toporia_library", "--collect-data", "toporia_library",
               "--collect-submodules", "toporia_gui", "--collect-data", "toporia_gui",
               "--copy-metadata", "toporia",
               "--hidden-import", "matplotlib.backends.backend_qtagg",
               # Never bundled: test and development tools.
               "--exclude-module", "pytest", "--exclude-module", "ruff", "--exclude-module", "PyInstaller"]
    for source, target in data:
        command += ["--add-data", f"{ROOT / source}{sep}{target}"]
    print(" ".join(command[:6]), "…")
    subprocess.run(command, check=True, cwd=ROOT)


def smoke_test(exe):
    result = subprocess.run([str(exe), "--smoke-test"], capture_output=True, text=True, timeout=600,
                            env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"})
    output = (result.stdout + result.stderr).strip()
    print(output[-2000:])
    if result.returncode != 0 or "smoke test passed" not in output:
        raise SystemExit(f"The built program failed its smoke test (exit {result.returncode}).")


def archive(folder):
    target = DIST / f"{NAME}-{__version__}-windows.zip"
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zipped.write(path, Path(NAME) / path.relative_to(folder))
    return target


def main():
    if sys.platform != "win32":
        raise SystemExit("Build the Windows program on Windows.")
    for folder in (DIST / NAME, BUILD):
        shutil.rmtree(folder, ignore_errors=True)
    pyinstaller()
    folder = DIST / NAME
    exe = folder / f"{NAME}.exe"
    # The stdout of a windowed program is not a console; the smoke test reads it through a pipe.
    smoke_test(exe)
    zipped = archive(folder)
    size = zipped.stat().st_size / 1e6
    print(f"{zipped}  ({size:.0f} MB)")


if __name__ == "__main__":
    main()
