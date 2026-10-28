# plugins/filters/heaviside.py — HeavisideFilter (projection, binarisation with beta continuation)
#
# Maps intermediate densities toward crisp 0/1 values using:
#   xf = (tanh(β·η) + tanh(β·(x − η))) / (tanh(β·η) + tanh(β·(1 − η)))
#
# where η is the threshold (default 0.5) and β controls sharpness.
# At β=1 the mapping is nearly linear; at β=32 it approaches a step function.
#
# β is ramped up via the continuation scheme to avoid local minima:
#   call step(iteration) each optimisation iteration.
# step() doubles β every beta_interval iterations, capped at beta_max.
# Until β reaches beta_max the filter reports continuing(), and the engine does
# not stop on its tolerance: a design converged at a soft projection is not
# the answer to the sharp one.
#
# β and η may also be driven by a schedule (solver.schedules, e.g. a
# geometric one on "filters[1].beta"); the built-in doubling then stands
# aside, so the two never fight over β.
#
# Backward pass (pointwise chain rule):
#   dx = β·sech²(β·(x − η)) / num
#
# Volume-preserving mode (eta_mode = "volume_preserving"):
#   a fixed η makes the projection change the volume (η = 0.5 adds material
#   where the field is mostly grey above 0.5, and so on), which the optimiser
#   then has to fight.  Instead η is found on every forward pass so that
#
#       mean(projected) = mean(input)
#
#   Projected volume falls monotonically as η rises (η = 0 gives a field
#   above the input, η = 1 one below it), so bisection on [0, 1] always
#   brackets the root.  The backward pass must include how η moves with the
#   input.  With p_j = ∂ρ̄_j/∂x_j and S = Σ ∂ρ̄_i/∂η, differentiating the
#   volume equation gives dη/dx_j = (1 − p_j) / S and so
#
#       out_j = s_j·p_j + (Σ_i s_i ∂ρ̄_i/∂η) · (1 − p_j) / S
#
#   Sketch:   x ──bisect η──> η(x) ──project──> ρ̄,  mean ρ̄ = mean x
#
#   At a design whose every element is exactly 0 or 1, S = 0: P(0, η) = 0 and
#   P(1, η) = 1 for every η, so every threshold preserves the volume and η is
#   not defined.  Two cases:
#     - uniform (all solid or all void): any admissible perturbation δx keeps
#       Σ P(x_j + δx_j, η) = Σ (x_j + δx_j) only if P'(0 or 1, η) = 1 for the
#       perturbed elements, so ρ̄ = x to first order: the derivative is the identity;
#     - mixed 0/1: the first-order response depends on the direction of δx (how
#       much is added at 0 versus removed at 1), so no gradient exists and the
#       run stops with an error.  Updaters whose designs are always exactly 0/1
#       (binary_designs) are refused at setup when the projection is the first
#       filter; behind a density filter their designs arrive with grey boundaries.
#   Exactly-binary elements contribute exactly zero to S (their ∂P/∂η vanishes
#   identically), so those terms are set to zero rather than kept as rounding noise.
#
# References: Xu, Cai & Cheng, SMO 41 (2010) 495-505; Ferrari & Sigmund,
#   "A new generation 99 line Matlab code ... (top99neo)", SMO 62 (2020)
#   2211-2228, which solves for η the same way (open code: top99neo.m).

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.filter import Filter


class HeavisideFilter(Filter):
    """Heaviside projection with beta continuation.

    Parameters
    ----------
    beta          : initial sharpness (≥1, typically start at 1)
    eta           : threshold position (0.5 maps x=0.5 → xf=0.5)
    beta_max      : upper limit for beta ramp (32 is a common choice)
    beta_interval : number of iterations between each doubling of beta
    eta_mode      : "fixed" uses eta as given; "volume_preserving" solves for
                    eta every pass so the projection keeps the mean density

    The volume-preserving threshold has no derivative at a mixed 0/1 design;
    such a design stops the run with an error, and updaters that only produce
    0/1 designs are refused when this projection is the first filter. All-solid
    and all-void designs use the exact limit (the identity).
    """

    name = "heaviside"
    label = "Heaviside projection"
    use_when = (
        "After a density filter, when you want a crisp black-and-white design instead of grey material. "
        "Raise beta gradually (a continuation schedule); a sharp start makes the optimiser stall. The "
        "volume-preserving mode keeps the material budget unchanged; with 0/1-only updaters (TOBS, hard-kill "
        "BESO) put a density filter in front of it."
    )
    reference = (
        'J. K. Guest, J. H. Prevost, T. Belytschko, "Achieving minimum length scale in topology'
        ' optimization using nodal design variables and projection functions", IJNME 61 (2004)'
        ' 238-254; the tanh form with threshold eta from F. Wang, B. S. Lazarov, O. Sigmund, "On'
        ' projection methods, convergence and robust formulations in topology optimization", Struct.'
        ' Multidisc. Optim. 43 (2011) 767-784.'
        ' Papers: https://doi.org/10.1002/nme.1064 https://doi.org/10.1007/s00158-010-0602-y https://doi.org/10.1007/s00158-020-02629-w'
    )
    dims = (2, 3)           # pointwise: any dimension
    order = 30
    params = (
        Param("beta", 1.0, "beta", "Initial projection sharpness. 1 is nearly linear.",
              min=0.1, max=128.0, step=1.0, decimals=1),
        Param("eta", 0.5, "eta", "Projection threshold: densities above it are pushed toward solid.",
              min=0.0, max=1.0, step=0.05, decimals=2),
        Param("beta_max", 32.0, "beta max", "Upper limit of the beta continuation.",
              min=1.0, max=512.0, step=8.0, decimals=0),
        Param("beta_interval", 25, "beta interval", "Iterations between each doubling of beta.",
              min=1, max=500),
        Param("eta_mode", "fixed", "Threshold mode",
              "Fixed: use the threshold as given. Volume preserving: pick the threshold every "
              "iteration so the projection does not change the volume (Xu, Cai & Cheng 2010).",
              choices=(("fixed", "Fixed"), ("volume_preserving", "Volume preserving"))),
    )

    schedulable = ("beta", "eta")

    def __init__(self, beta=1.0, eta=0.5, beta_max=32.0, beta_interval=25, eta_mode="fixed"):
        if eta_mode not in ("fixed", "volume_preserving"):
            raise ValueError(f"eta_mode must be 'fixed' or 'volume_preserving', got {eta_mode!r}")
        self.eta_mode      = eta_mode
        self.beta         = float(beta)
        self.eta           = float(eta)
        self.beta_max      = float(beta_max)
        self.beta_interval = int(beta_interval)
        self._beta_scheduled = False   # a schedule drives beta: the built-in doubling stands aside

    def setup(self, problem, solver):
        if self.eta_mode != "volume_preserving" or solver is None:
            return
        from toporia.plugins.methods import method_class
        updater = getattr(method_class(solver.method), "updater", None)
        first = solver.filter_specs[0].get("type") if solver.filter_specs else None
        # Behind another filter a 0/1 design arrives with grey boundaries, where the derivative exists.
        if getattr(updater, "binary_designs", False) and first == self.name:
            raise ValueError(f"Volume-preserving Heaviside projection as the first filter cannot be used with "
                             f"{updater.label}: its designs are exactly 0/1, where the volume-preserving threshold "
                             "has no derivative. Put a density filter in front, or use the fixed threshold mode.")

    def set_parameter(self, name, value):
        """Set beta or eta during a run; a scheduled beta switches the built-in doubling off."""
        if name == "beta":
            self._beta_scheduled = True
        setattr(self, name, float(value))

    def _project(self, x, e):
        """The projected field for threshold e (a scalar)."""
        b   = self.beta
        num = np.tanh(b * e) + np.tanh(b * (1.0 - e))
        return (np.tanh(b * e) + np.tanh(b * (x - e))) / num

    def _volume_preserving_eta(self, x):
        """The threshold at which the projection keeps the mean of x (bisection on [0, 1])."""
        target, lo, hi = float(np.mean(x)), 0.0, 1.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if np.mean(self._project(x, mid)) > target:
                lo = mid        # too much material: raise the threshold
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def _d_eta(self, x, e):
        """∂(projected)/∂η, elementwise, at threshold e."""
        b = self.beta
        t0, t1, tx = np.tanh(b * e), np.tanh(b * (1.0 - e)), np.tanh(b * (x - e))
        num  = t0 + t1
        dnum = b * ((1.0 - t0 ** 2) - (1.0 - t1 ** 2))
        dtop = b * ((1.0 - t0 ** 2) - (1.0 - tx ** 2))
        return (dtop * num - (t0 + tx) * dnum) / num ** 2

    def forward(self, x):
        if self.eta_mode == "volume_preserving":
            self.eta = self._volume_preserving_eta(x)    # kept so a run can report it
        b, e = self.beta, self.eta
        num  = np.tanh(b * e) + np.tanh(b * (1.0 - e))
        return (np.tanh(b * e) + np.tanh(b * (x - e))) / num

    def backward(self, x_in, sensitivity):
        if self.eta_mode == "volume_preserving":
            b   = self.beta
            e   = self._volume_preserving_eta(x_in)   # x_in is what entered forward(): the same root
            num = np.tanh(b * e) + np.tanh(b * (1.0 - e))
            p   = b * (1.0 - np.tanh(b * (x_in - e)) ** 2) / num
            # ∂P/∂η vanishes identically at x = 0 and x = 1 (see the header).
            d_eta = np.where((x_in == 0.0) | (x_in == 1.0), 0.0, self._d_eta(x_in, e))
            total = np.sum(d_eta)
            if total == 0.0:
                if np.all(x_in == x_in.flat[0]) and x_in.flat[0] in (0.0, 1.0):
                    return np.array(sensitivity, dtype=float)    # all solid or all void: the identity limit
                raise ValueError("Volume-preserving Heaviside projection has no derivative here: every element is "
                                 "0 or 1 (or so far from the threshold at this beta that the threshold no longer "
                                 "moves), so any threshold preserves the volume. Use the fixed threshold mode.")
            return sensitivity * p + np.sum(sensitivity * d_eta) * (1.0 - p) / total
        b, e = self.beta, self.eta
        num  = np.tanh(b * e) + np.tanh(b * (1.0 - e))
        dx   = b * (1.0 - np.tanh(b * (x_in - e)) ** 2) / num
        return sensitivity * dx

    def step(self, iteration):
        """Double beta every beta_interval iterations, capped at beta_max.
        Called by FilterChain.step() once per optimisation iteration."""
        if self._beta_scheduled:
            return
        if iteration > 0 and iteration % self.beta_interval == 0:
            self.beta = min(self.beta * 2.0, self.beta_max)

    def continuing(self):
        """True until the built-in doubling has brought beta to beta_max."""
        return not self._beta_scheduled and self.beta < self.beta_max
