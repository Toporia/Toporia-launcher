"""Maximise signed output displacement using one virtual-load adjoint.

J = -sum w*l^T*u, K*u=f, K*psi=l.
dJ/d(rho_e) = dE/d(rho_e) * sum w*psi_e^T*KE*u_e.
Fixed port springs enter K but have zero density derivative. Mixed signs are
essential to mechanisms: use MMA or another general-gradient optimiser.
Own implementation from Sigmund (1997), not copied source code.
Papers: https://doi.org/10.1080/08905459708945415
"""

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.physics import POINT_DISPLACEMENT, STRESS
from toporia.framework.parts.response import OBJECTIVE_ROLE, Response, ResponseValue


class OutputDisplacement(Response):
    """The displacement of an output port in a chosen direction; minimising its negative makes a mechanism move."""
    name = "output_displacement"
    label = "Output displacement (maximise)"
    use_when = (
        "For compliant mechanisms: makes an output port move in a chosen direction (needs port springs "
        "and MMA-type updaters, because the sensitivities change sign)."
    )
    order = 17
    roles = (OBJECTIVE_ROLE,)
    dims = (2,)
    requires = (POINT_DISPLACEMENT, STRESS)
    params = (
        Param("x", 60.0, "Output x", "Output port coordinate, snapped to the nearest mesh node.",
              min=0.0, max=1e6, step=1.0, decimals=3, units="mm"),
        Param("y", 10.0, "Output y", "Output port coordinate from the bottom of the domain.",
              min=0.0, max=1e6, step=1.0, decimals=3, units="mm"),
        Param("angle", 180.0, "Output direction", "Direction of desired motion: 0 is +x, 90 is +y.",
              min=-360.0, max=360.0, step=15.0, decimals=1, units="deg"),
    )
    advice = ("Maximises displacement in the chosen direction; use a general-gradient updater such as MMA. "
              "Port springs limit displacement. This is linear small-displacement analysis.")
    reference = (
        'O. Sigmund, "On the Design of Compliant Mechanisms Using Topology Optimization", '
        'Mechanics of Structures and Machines 25 (1997) 493-524. '
        'Papers: https://doi.org/10.1080/08905459708945415'
    )

    def setup(self, physics, problem, settings):
        super().setup(physics, problem, settings)
        self.probe = physics.point_probe(settings["x"], settings["y"], settings["angle"])

    def evaluate(self, state, gradient=True):
        physics = self.physics
        displacement = sum(weight * physics.probe_displacement(state, case, self.probe)
                           for case, weight in enumerate(state.weights))
        reported = {"output_displacement": displacement}
        if not gradient:
            return ResponseValue(-displacement, reported=reported)
        adjoint = physics.adjoint(state, self.probe)
        mutual = np.zeros_like(state.density)
        for case, weight in enumerate(state.weights):
            mutual += weight * physics.mutual_energy(state, case, adjoint)
        return ResponseValue(-displacement, physics.stiffness_slope(state) * mutual, reported=reported)
