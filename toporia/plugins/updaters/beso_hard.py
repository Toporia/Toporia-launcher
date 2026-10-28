# plugins/updaters/beso_hard.py — hard-kill BESO.
#
# Same ranking, same evolutionary volume schedule, same addition limit and the
# same convergence test as soft-kill BESO (beso.py, which this subclasses and
# does not copy); the one difference is what a removed element becomes.
#
#   soft kill   a removed element keeps a small residual density
#               (`void_density`, 0.001), so it still has a sensitivity of its own
#               and the ranking can bring it back directly.
#   hard kill   a removed element is set to the void bound itself (0), which the
#               stiffness interpolation maps to the minimum stiffness Emin: to the
#               solver it is absent.  Under SIMP its own sensitivity is exactly
#               p·0^(p−1)·uᵀKu = 0 (it carries no strain energy), so it can only come
#               back through the FILTERED sensitivities of its solid neighbours —
#               the filter chain's adjoint has already mixed them into its entry.
#               With an empty filter chain a hard-killed element can never return,
#               and the iteration degenerates into one-way ESO; use a density or
#               sensitivity filter (as for soft-kill BESO).
#
# That dependence on the filter is the point of the variant, and the reason Zhou &
# Rozvany (2001) criticised hard-kill ESO: whether an element is re-admitted is
# decided by the filter's smoothing rather than by its own response, and removal
# can sever the load path irrecoverably.  Huang & Xie (2010) address it with the
# sensitivity filter and the sensitivity averaging that beso.py already applies.
# Elements are not deleted from the mesh (the stiffness matrix would change size
# every iteration); Emin stiffness is the standard equivalent.
#
# References
# ----------
# X. Huang, Y. M. Xie, "Evolutionary Topology Optimization of Continuum
# Structures: Methods and Applications", Wiley (2010).
# M. Zhou, G. I. N. Rozvany, "On the validity of ESO type methods in topology
# optimization", Structural and Multidisciplinary Optimization 21 (2001) 80–83.

from toporia.plugins.updaters.beso import BESOUpdater


class HardKillBESOUpdater(BESOUpdater):
    """Hard-kill BESO: removed elements sit exactly at the void bound."""

    name = "beso_hard"
    binary_designs = True
    reference = (
        'X. Huang and Y. M. Xie, Evolutionary Topology Optimization of Continuum Structures, '
        'Wiley 2010 (hard-kill BESO); critique: M. Zhou and G. I. N. Rozvany, Struct. '
        'Multidisc. Optim. 21 (2001) 80-83.'
        ' Papers: https://doi.org/10.1002/9780470689486 https://doi.org/10.1007/s001580050170'
    )
    label = "BESO (hard kill)"
    use_when = (
        "Like soft-kill BESO, but removed elements are fully void; mainly for comparison with the hard-"
        "kill literature."
    )
    order = 61
    # No residual density to set: removed means void.
    params = tuple(p for p in BESOUpdater.params if p.name != "void_density")

    def initialize(self, model, settings):
        super().initialize(model, {**settings, "void_density": 0.0})
