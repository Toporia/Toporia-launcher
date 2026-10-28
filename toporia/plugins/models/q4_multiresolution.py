"""Fine-density/coarse-displacement Q4 model, independently derived from MTOP.

A coarse displacement space is a subspace of the fine one, so it always predicts
a stiffer structure than the fine analysis would.  With features smaller than one
analysis cell the optimiser exploits that gap: material islands joined only
through the coarse displacement interpolation look stiff and are not.  On the MBB
beam a filter radius of 0.75 analysis cells gives coarse/fine compliance 0.49 at
coarsening 4 (the fine-mesh design is twice as flexible as plain Q4's); at one
analysis cell and above the ratio is 0.96-0.99 and the design matches plain Q4.
So a run with coarsening > 1 needs a smoothing filter (density or PDE) of at least
one analysis cell, which is the length-scale rule of Groen et al. (2017) for
linear displacement elements.
"""

from toporia.plugins.physics.q4_multiresolution import Q4Multiresolution

from .assembled import AssembledModel

#: Filters that smooth the physical density, and the parameters that set their radius in fine cells.
SMOOTHING = {"density": ("rmin",), "pde": ("rmin",), "pde_anisotropic": ("rmin_x", "rmin_y")}


def smoothing_radius(filter_specs):
    """The largest radius, in fine cells, of the smoothing filters in a chain; 0 when there is none."""
    from toporia.plugins.filters import FILTERS
    radii = [0.0]
    for spec in filter_specs:
        kind = spec.get("type", "density")
        if kind in SMOOTHING:
            defaults = {p.name: p.default for p in FILTERS.get(kind).params}
            radii.append(min(float(spec.get(name, defaults[name])) for name in SMOOTHING[kind]))
    return max(radii)


class Q4MultiresolutionModel(AssembledModel):
    """Nested 2-D multiresolution elasticity; fine-grid filters and representations."""

    name = "q4_multiresolution"
    label = Q4Multiresolution.label
    use_when = (
        "To get a finer design than the analysis mesh at lower cost. Needs a density or PDE filter radius of at "
        "least one analysis cell (the coarsening factor, in fine cells); smaller features look stiffer than they are."
    )
    reference = (Q4Multiresolution.reference + ' Length-scale rule: J. P. Groen, M. Langelaar, O. Sigmund, '
                 'M. Ruess, "Higher-order multi-resolution topology optimization using the finite cell method", '
                 'IJNME 110 (2017) 903-920.')
    order = 10
    physics = Q4Multiresolution

    def initialize(self, problem, solver, settings):
        coarsening = int(settings.get("coarsening", 1))
        radius = smoothing_radius(solver.filter_specs)
        if coarsening > 1 and radius < coarsening:
            raise ValueError(
                f"Multiresolution with coarsening {coarsening} needs a density or PDE filter radius of at least "
                f"{coarsening} fine cells (one analysis cell); the chain has {radius:g}. Smaller features are "
                "artificially stiff on the coarse displacement grid (Groen et al. 2017).")
        super().initialize(problem, solver, settings)
