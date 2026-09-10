# problems/__init__.py — registry of available topology-optimisation problems
#
# To add a new problem:
#   1. Create a file in this folder (e.g. my_bridge.py) that defines get_config()
#      returning a TopOptConfig.
#   2. Add an entry to PROBLEMS below: "Display Name" -> "module_name"
#   3. If it should be the startup default, update DEFAULT_PROBLEM.
#
# get_config(name) loads the matching module on demand and calls its get_config().
# This lazy import means the package can be imported before the solver is ready.

DEFAULT_PROBLEM = "mbb_beam"

PROBLEMS = {
    # ── Canonical benchmarks ──────────────────────────────────────────────────
    "MBB Beam":             "mbb_beam",          # default — half-symmetry simply-supported beam
    "Cantilever":           "cantilever",        # fixed left edge, midpoint right load
    "Three-Point Bending":  "three_point_bending",
    "Standard Bar":         "standard_bar",      # cantilever-like, fixed left, corner load
    # ── Application example ───────────────────────────────────────────────────
    "Drone Arm":                   "drone_arm",
    "Drone Arm (Camera View)":     "drone_arm_camera_view",
    "Drone Arm (Point Loads)":     "drone_arm_point_loads",
}

# GUI dropdown alias — window.py imports this name
CONFIGURATIONS = PROBLEMS


def get_config(name: str):
    """Return a TopOptConfig for the named problem.

    Parameters
    ----------
    name : str
        Key from the PROBLEMS registry, e.g. ``"MBB Beam"``.

    Returns
    -------
    TopOptConfig
    """
    import importlib
    if name not in PROBLEMS:
        raise KeyError(f"Unknown problem {name!r}. Available: {list(PROBLEMS)}")
    mod = importlib.import_module("." + PROBLEMS[name], package=__package__)
    return mod.get_config()


def get_default_config():
    """Return a TopOptConfig for the default startup problem (MBB Beam)."""
    for name, module_name in PROBLEMS.items():
        if module_name == DEFAULT_PROBLEM:
            return get_config(name)
    raise KeyError(
        f"DEFAULT_PROBLEM={DEFAULT_PROBLEM!r} is not registered in PROBLEMS. "
        f"Available: {list(PROBLEMS.values())}"
    )
