# plugins/updaters/ptoc.py — proportional topology optimisation, the original PTOc algorithm.
#
# Connects to the framework as an Updater.  Each iteration hands the whole
# material budget out again, in proportion to each element's compliance, and
# blends the result with the previous design.  No gradient-based step at all:
#
#     c_e     = E(x_e) u_eᵀ k₀ u_e                     element compliance
#     RM      = V*, x_opt = 0                           remaining material
#     repeat while RM > tol:
#         x_opt += filter( RM · c^q / Σ c^q )           allocate, then smooth the increment
#         x_opt  = clip(x_opt, x_min, 1)
#         RM     = V* − Σ x_opt
#     x_new = α x + (1 − α) x_opt                       history blend
#
# The filter is PTOc's own (weights max(0, r − distance), in elements, normalised
# per element), applied to each allocated increment, so the run takes no filter
# chain.  The element compliance is read exactly from the compliance gradient:
# with no filters, ∂C/∂x_e = −E′(x_e) u_eᵀk₀u_e, so c_e = −E(x_e)/E′(x_e) · ∂C/∂x_e.
#
# Checked against the unchanged author code (PLOS ONE S2, PTOc_mbb.m, captured
# in tests/references/paper_ptoc.json): on the 120 x 40 half-MBB of Figure 3 all
# 169 printed compliances agree to their two printed decimals and the final
# density agrees to 1e-8.  plugins/updaters/pto.py is a different, sensitivity-
# proxy variant and is kept as such.
#
# Reference: E. Biyikli, A. C. To, "Proportional topology optimization: a new
# non-sensitivity method for solving stress constrained and minimum compliance
# problems and its implementation in MATLAB", PLoS ONE 10 (2015) e0145041.

import numpy as np
from scipy.ndimage import correlate

from toporia.framework.params import Param
from toporia.framework.parts.updater import Updater

#: PTOc's lower density bound and the material left unplaced that ends the allocation loop.
X_MIN, REMAINING_TOL, MAX_ALLOCATIONS = 1e-9, 1e-3, 1000


def ptoc_kernel(rmin, ndim):
    """PTOc's filter weights max(0, rmin − distance) over the neighbouring elements."""
    reach = int(np.ceil(rmin)) - 1
    offsets = np.indices((2 * reach + 1,) * ndim) - reach
    return np.maximum(0.0, rmin - np.sqrt(np.sum(offsets ** 2, axis=0)))


class PTOcUpdater(Updater):
    """The original PTOc: material handed out in proportion to element compliance, filtered, blended."""

    name = "ptoc"
    label = "PTOc (original proportional TO)"
    use_when = (
        "To reproduce proportional topology optimisation as published: no sensitivities, crisp-ish designs, "
        "compliance only. It does its own filtering, so run it without a filter chain."
    )
    reference = (
        'E. Biyikli, A. C. To, "Proportional topology optimization: a new non-sensitivity method for solving '
        'stress constrained and minimum compliance problems and its implementation in MATLAB", PLoS ONE 10 '
        '(2015) e0145041; checked against the authors\' PTOc_mbb.m (PLOS S2).'
        ' Papers: https://doi.org/10.1371/journal.pone.0145041'
    )
    order = 81
    params = (
        Param("q", 1.0, "Exponent q", "Material goes to each element in proportion to its compliance raised to q.",
              min=0.1, max=5.0, step=0.1, decimals=2),
        Param("alpha", 0.5, "History weight alpha",
              "The new design is alpha times the old one plus (1 - alpha) times the new allocation.",
              min=0.0, max=0.95, step=0.05, decimals=2),
        Param("filter_radius", 1.5, "Filter radius [el]", "Radius of PTOc's own filter on each allocated increment.",
              min=1.0, max=10.0, step=0.1, decimals=2),
    )
    objectives = ("compliance",)
    max_constraints = 0
    needs_element_densities = True
    own_filter = True
    needs_material_law = True
    dims = (2, 3)

    def initialize(self, model, settings):
        if getattr(model, "material", None) is None:
            raise ValueError("PTOc needs a model with a material law (element compliance from its stiffness)")
        if model.pipeline.chain is not None:
            raise ValueError("PTOc filters its own allocation: remove the filter chain (filter_specs=[])")
        self.model, self.q, self.alpha = model, settings["q"], settings["alpha"]
        self.lb, self.ub = model.bounds()
        self.lower = np.maximum(self.lb, X_MIN)
        kernel = ptoc_kernel(settings["filter_radius"], self.lb.ndim)
        self._filter = lambda field: correlate(field, kernel, mode="constant") / self._weights
        self._weights = correlate(np.ones_like(self.lb), kernel, mode="constant")

    def element_compliance(self, x, gradient):
        """c_e = −E(x_e)/E′(x_e) · ∂C/∂x_e (exact with no filter chain); zero where the slope vanishes."""
        scenario = self.model.problem.scenario
        stiffness = self.model.material.stiffness(x, scenario.E0, scenario.Emin)
        slope = self.model.material.slope(x, scenario.E0, scenario.Emin)
        with np.errstate(divide="ignore", invalid="ignore"):
            c = np.where(slope > 0, -stiffness / slope * gradient, 0.0)
        return np.maximum(c, 0.0) * (self.ub > 0)

    def update(self, x, evaluation, completed):
        weights = self.element_compliance(x, np.asarray(evaluation.objective_gradient, dtype=float)) ** self.q
        if not np.sum(weights) > 0:
            return x
        budget = self.model.volume_limit
        target, remaining = np.zeros_like(x), budget
        for _ in range(MAX_ALLOCATIONS):
            if remaining <= REMAINING_TOL:
                break
            target = np.clip(target + self._filter(remaining * weights / np.sum(weights)), self.lower, self.ub)
            remaining = budget - self.model.volume_of(target)
        return self.alpha * x + (1.0 - self.alpha) * target
