# filter_heaviside.py — HeavisideFilter (projection, binarisation with beta continuation)
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
#
# Backward pass (pointwise chain rule):
#   dx = β·sech²(β·(x − η)) / num

import numpy as np

from toporia.core.params import Param

from .filter_base import Filter


class HeavisideFilter(Filter):
    """Heaviside projection with beta continuation.

    Parameters
    ----------
    beta          : initial sharpness (≥1, typically start at 1)
    eta           : threshold position (0.5 maps x=0.5 → xf=0.5)
    beta_max      : upper limit for beta ramp (32 is a common choice)
    beta_interval : number of iterations between each doubling of beta
    """

    name = "heaviside"
    label = "Heaviside projection"
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
    )

    def __init__(self, beta=1.0, eta=0.5, beta_max=32.0, beta_interval=25):
        self.beta          = float(beta)
        self.eta           = float(eta)
        self.beta_max      = float(beta_max)
        self.beta_interval = int(beta_interval)

    def setup(self, problem, solver): pass

    def forward(self, x):
        b, e = self.beta, self.eta
        num  = np.tanh(b * e) + np.tanh(b * (1.0 - e))
        return (np.tanh(b * e) + np.tanh(b * (x - e))) / num

    def backward(self, x_in, sensitivity):
        b, e = self.beta, self.eta
        num  = np.tanh(b * e) + np.tanh(b * (1.0 - e))
        dx   = b * (1.0 - np.tanh(b * (x_in - e)) ** 2) / num
        return sensitivity * dx

    def step(self, iteration):
        """Double beta every beta_interval iterations, capped at beta_max.
        Called by FilterChain.step() once per optimisation iteration."""
        if iteration > 0 and iteration % self.beta_interval == 0:
            self.beta = min(self.beta * 2.0, self.beta_max)
