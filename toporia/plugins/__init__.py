"""library — the swappable parts.

Everything here is an implementation the engine selects at run time.  Each
subpackage is scanned for plugins, so extending one means adding a file:

    fe/        finite element solvers, and the physics engines built on them
    filters/   density filters and the filter pipeline
    models/    what is optimised: design -> objective, volume, constraints and gradients
    updaters/  how a design moves: OC, MMA, SiMPL, BESO, pyMOTO's MMA and GCMMA, SciPy's SLSQP
    responses/ what a scenario can minimise or constrain: compliance, volume, stress
    methods/   "<model>+<updater>" pairings (built on demand), and the RBF level set
    problems/  benchmark and application presets
    catalog.py every numeric value a setup lets you sweep, as parameter paths

Extending the library never requires editing core/ or engine/.  See README.md
here for the map of each part, and docs/writing-plugins.md for how to add one.
"""
