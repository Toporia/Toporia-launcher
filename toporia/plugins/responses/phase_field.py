"""Two-phase, fixed-load perimeter-regularised compliance.

J = C/C_full + gamma * mean(epsilon/2 |grad rho|^2 + W(rho)/epsilon),
W(rho)=rho^2(1-rho)^2. The mean is the domain-normalised physical integral
on uniform cells. epsilon and gamma are in mm, so J is dimensionless in
2-D and 3-D. The gradient term measures internal interfaces (no outer flux).

This independently implements the diffuse-interface energy principle of
Bourdin & Chambolle (2003), also explained in Takezawa et al. (2010), Section
2.3. It uses Toporia's material law, finite-volume discretisation and existing
optimisers. It is not the former paper's three-phase pressure-load model or
the latter's shape-only, tilted-well Allen-Cahn update. No code is copied.
"""

import numpy as np
from scipy.sparse import csc_matrix, eye

from toporia.framework.params import Param
from toporia.framework.parts.physics import ELASTIC_ENERGY
from toporia.framework.parts.response import OBJECTIVE_ROLE, Response, ResponseValue
from toporia.plugins.filters.pde import _chain
from toporia.plugins.filters.pde_anisotropic import _neumann_laplacian

from .compliance import Compliance


def physical_laplacian(shape, spacings):
    """Conservative cell-centred -Laplacian with zero outer flux, C order."""
    if len(shape) != len(spacings) or any(n < 1 for n in shape):
        raise ValueError("Each positive grid dimension needs one physical spacing")
    if any(not np.isfinite(h) or h <= 0 for h in spacings):
        raise ValueError("Physical spacings must be finite and positive")
    identities = [eye(n, format="csc") for n in shape]
    matrix = csc_matrix((int(np.prod(shape)), int(np.prod(shape))))
    for axis, spacing in enumerate(spacings):
        factors = list(identities)
        factors[axis] = _neumann_laplacian(shape[axis])
        matrix = matrix + _chain(factors)/spacing**2
    return matrix.tocsc()


def phase_energy(density, laplacian, epsilon, gradient=True):
    """Domain-mean Modica-Mortola energy and exact discrete density gradient.

Multiply the value by the physical domain measure to recover the integral.
The resolved planar-interface energy tends to sqrt(2)/6 per unit interface
measure for this double-well convention.
"""
    if not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("Phase-field interface length must be finite and positive")
    rho = np.asarray(density, dtype=float).ravel()
    diffusion = laplacian @ rho
    well = rho*rho*(1-rho)**2
    energy = (0.5*epsilon*np.dot(rho, diffusion) + np.sum(well)/epsilon)/rho.size
    slope = None
    if gradient:
        slope = (epsilon*diffusion + 2*rho*(1-rho)*(1-2*rho)/epsilon)/rho.size
        slope = slope.reshape(density.shape)
    return float(energy), slope


class PhaseFieldCompliance(Response):
    """Compliance plus a diffuse-interface (perimeter) penalty, so interfaces stay few and smooth."""
    name = "phase_field"
    label = "Phase-field regularised compliance"
    use_when = (
        "When you want stiffness and fewer, smoother interfaces at once; the perimeter weight trades one "
        "for the other."
    )
    reference = (
        'B. Bourdin and A. Chambolle, "Design-dependent loads in topology '
        'optimization", ESAIM: COCV 9 (2003) 19-48; A. Takezawa, S. Nishiwaki '
        'and M. Kitamura, JCP 229 (2010) 2697-2718, Section 2.3. Independent '
        'two-phase, fixed-load energy with finite-volume gradients and Toporia '
        'optimisers; not a pressure-load or tilted-well Allen-Cahn port.'
        ' Papers: https://doi.org/10.1051/cocv:2002070 https://doi.org/10.1016/j.jcp.2009.12.017'
    )
    order = 11
    roles = (OBJECTIVE_ROLE,)
    requires = (ELASTIC_ENERGY,)
    dims = (2, 3)
    params = (
        Param("interface_width", 1.0, "Interface length epsilon",
              "Physical interface coefficient; a resolved planar 10%-90% transition is about 3.11 times this length.",
              min=0.01, max=100.0, decimals=3, units="mm"),
        Param("perimeter_weight", 5.0, "Perimeter weight",
              "Weight of the domain-mean diffuse-interface energy. Larger values favour fewer internal interfaces; zero recovers normalised compliance.",
              min=0.0, max=1000.0, decimals=3, units="mm"),
    )
    advice = (
        "Phase field minimises normalised compliance plus a diffuse-interface energy. "
        "Use a general gradient optimiser such as MMA; OC's sign assumption does not apply. "
        "No density filter is needed. Resolve the interface over several cells; "
        "the phase length is not a guaranteed minimum feature size."
    )

    def setup(self, physics, problem, settings):
        super().setup(physics, problem, settings)
        self.epsilon = settings["interface_width"]
        self.weight = settings["perimeter_weight"]
        spacings = (problem.dy, problem.dx) if len(problem.shape) == 2 else (problem.dz, problem.dy, problem.dx)
        self.laplacian = physical_laplacian(problem.shape, spacings)
        self.compliance = Compliance()
        self.compliance.setup(physics, problem, {})
        # A fixed reference, independent of the current trial design and its
        # gradient. The selected material law, springs and case weights apply.
        full = physics.solve(problem.upper_bound)
        self.reference_compliance = self.compliance.evaluate(full, gradient=False).value
        if not np.isfinite(self.reference_compliance) or self.reference_compliance <= 0:
            raise ValueError("Phase-field normalisation needs positive full-material compliance")

    def evaluate(self, state, gradient=True):
        compliance = self.compliance.evaluate(state, gradient=gradient)
        energy, slope = phase_energy(state.density, self.laplacian, self.epsilon, gradient)
        normalised = compliance.value/self.reference_compliance
        value = normalised+self.weight*energy
        sensitivity = None
        if gradient:
            sensitivity = compliance.gradient/self.reference_compliance+self.weight*slope
        return ResponseValue(value, sensitivity,
                             reported={"normalised_compliance": normalised,
                                       "phase_energy": self.weight*energy})
