"""library — the swappable parts.

Everything here is an implementation the engine selects at run time.  Each
subpackage is scanned for plugins, so extending one means adding a file:

    fe/        finite element solvers
    filters/   density filters and the filter pipeline
    models/    what is optimised: design -> objective, volume and gradients
    updaters/  how a design moves: OC, MMA, pyMOTO's MMA and GCMMA
    responses/ what a scenario can minimise or constrain: compliance, volume, stress
    methods/   the selectable methods: model + updater pairings, and the level set
    problems/  benchmark and application presets

Extending the library never requires editing core/ or engine/.
"""
