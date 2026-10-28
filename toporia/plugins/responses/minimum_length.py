"""Geometric minimum-length constraint on a filtered physical density field.

Zhou et al. (2015) indicators, using Dunning's (2018) standalone geometric
filter adaptation. rho is the physical, normalised phase indicator; b=H rho
uses a cone of radius half the requested feature length. Solid/void measures
are rho exp(-c |G b|^2) (1-b)^2 and its phase complement. A conservative
KS aggregate controls their nodal values against Dunning's 1-D tolerance
scale, rather than diluting a small feature in a global average.

G differentiates in units of the minimum cell spacing; c=(R/h_min)^4 times
a user scale. The complete discrete derivative includes H.T and G.T terms.
This is an independent cell-centred variant, not a three-field Zhou port.
Finite mesh resolution, gray fields and the 1-D nodal tolerance calibration
prevent treating it as a universal certificate of geometric minimum size.
"""

import numpy as np
from scipy.signal import convolve
from scipy.sparse import coo_matrix, csc_matrix, eye
from scipy.special import logsumexp

from toporia.framework.params import Param
from toporia.framework.parts.response import CONSTRAINT_ROLE, Response, ResponseValue
from toporia.plugins.filters.pde import _chain


def cone_kernel(radius, spacings, shape):
    """Symmetric physical-distance cone sampled at cell centres."""
    if not np.isfinite(radius) or radius < 2*max(spacings):
        raise ValueError("Minimum-length radius needs at least two cells in each direction; refine the mesh or increase the length")
    # Offsets beyond the array extent never enter a truncated neighbourhood.
    reaches = [min(int(np.ceil(radius/h))-1, n-1) for h, n in zip(spacings, shape, strict=True)]
    axes = [np.arange(-reach, reach+1)*h for reach, h in zip(reaches, spacings, strict=True)]
    coordinates = np.meshgrid(*axes, indexing="ij")
    distance = np.sqrt(sum(axis*axis for axis in coordinates))
    return np.maximum(radius-distance, 0.0)


def difference_matrix(n, scale):
    """Central differences inside, one-sided at each end, singleton derivative zero."""
    if n == 1:
        return csc_matrix((1, 1))
    rows, cols, values = [0, 0, n-1, n-1], [0, 1, n-2, n-1], [-1.0, 1.0, -1.0, 1.0]
    for i in range(1, n-1):
        rows.extend((i, i))
        cols.extend((i-1, i+1))
        values.extend((-0.5, 0.5))
    return coo_matrix((np.asarray(values)*scale, (rows, cols)), shape=(n, n)).tocsc()


class MinimumLength(Response):
    """Constraints that flag solid members and holes thinner than a requested length (geometric indicators)."""
    name = "minimum_length"
    label = "Minimum feature length (geometric)"
    use_when = (
        "When solid members or holes must not get thinner than a manufacturing size. The indicators are "
        "calibrated proxies, not a size certificate."
    )
    reference = (
        'M. Zhou, B. S. Lazarov, F. Wang and O. Sigmund, "Minimum length scale in '
        'topology optimization by geometric constraints", CMAME 293 (2015) '
        '266-282; P. D. Dunning, SMO 58 (2018) 155-169, standalone filter '
        'adaptation. Independent cell-centred physical-field variant with '
        'conservative nodal KS aggregation and a scaled 1-D tolerance; no code copied.'
        ' Papers: https://doi.org/10.1016/j.cma.2015.05.003 https://doi.org/10.1007/s00158-017-1883-1'
    )
    order = 36
    roles = (CONSTRAINT_ROLE,)
    requires = ()
    dims = (2, 3)
    params = (
        Param("phase", "solid", "Controlled phase", "Add one constraint for each phase when both are required.",
              choices=(("solid", "Solid members"), ("void", "Void features"))),
        Param("min_length", 10.0, "Requested feature length",
              "Physical feature length; the geometric cone radius is half this value. Resolve the radius over several cells.",
              min=0.01, max=1000.0, decimals=3, units="mm"),
        Param("limit", 1.0, "Nodal tolerance multiplier",
              "Multiplier of the paper's 1-D nodal tolerance scale. Larger values relax the constraint; calibrate on the actual mesh and geometry.",
              min=0.01, max=100.0, decimals=4),
        Param("decay_scale", 1.0, "Indicator decay scale",
              "Multiplier of (radius/minimum-cell-spacing)^4. Excessive decay can miss discrete medial regions.",
              min=0.01, max=10.0, decimals=3),
        Param("sharpness", 10.0, "KS sharpness factor",
              "Conservative aggregation exceeds the largest normalised nodal measure by at most 1/this factor.",
              min=2.0, max=100.0, decimals=2),
    )
    # Generic model checks use 3.33 mm cells, coarser than the default mesh.
    gradient_check_settings = {"min_length": 16.0}
    schedulable = ("limit",)

    def setup(self, physics, problem, settings):
        super().setup(physics, problem, settings)
        self.shape = problem.shape
        self.spacings = ((problem.dy, problem.dx) if len(self.shape) == 2
                         else (problem.dz, problem.dy, problem.dx))
        radius = settings["min_length"]/2
        self.kernel = cone_kernel(radius, self.spacings, self.shape)
        self.normaliser = convolve(np.ones(self.shape), self.kernel, mode="same", method="auto")
        h = min(self.spacings)
        self.decay = settings["decay_scale"]*(radius/h)**4
        # Maximum of t^4/(4*r^4)*exp(-c*t^2/r^4), 0 <= t <= r.
        # The paper's interior critical point leaves that interval at low c.
        r = radius/h
        t = min(r, np.sqrt(2)*r*r/np.sqrt(self.decay))
        self.reference_tolerance = t**4/(4*r**4)*np.exp(-self.decay*t*t/r**4)
        self.ks_beta = settings["sharpness"]*max(float(np.log(np.prod(self.shape))), 1.0)
        self.derivatives = []
        for axis, spacing in enumerate(self.spacings):
            factors = [eye(n, format="csc") for n in self.shape]
            factors[axis] = difference_matrix(self.shape[axis], h/spacing)
            self.derivatives.append(_chain(factors))

    def _filter(self, density):
        return convolve(density, self.kernel, mode="same", method="auto")/self.normaliser

    def _filter_adjoint(self, sensitivity):
        return convolve(sensitivity/self.normaliser, self.kernel, mode="same", method="auto")

    def measure(self, density, gradient=True):
        """Conservative normalised KS measure, full derivative and nodal values."""
        filtered = self._filter(density)
        spatial = [matrix @ filtered.ravel() for matrix in self.derivatives]
        exponential = np.exp(-self.decay*sum(component*component for component in spatial)).reshape(self.shape)
        solid = self.settings["phase"] == "solid"
        phase = density if solid else 1-density
        deficit = 1-filtered if solid else filtered
        local = phase*exponential*deficit**2
        tolerance = self.settings["limit"]*self.reference_tolerance
        logits = self.ks_beta*local/tolerance
        log_sum = float(logsumexp(logits))
        aggregate = log_sum/self.ks_beta
        if not gradient:
            return aggregate, None, local
        weights = np.exp(logits-log_sum)/tolerance
        sign = 1.0 if solid else -1.0
        direct = sign*exponential*deficit**2*weights
        filtered_gradient = -sign*2*phase*exponential*deficit*weights
        for matrix, component in zip(self.derivatives, spatial, strict=True):
            filtered_gradient += (matrix.T @ (-2*self.decay*(local*weights).ravel()*component)).reshape(self.shape)
        derivative = direct+self._filter_adjoint(filtered_gradient)
        return aggregate, derivative, local

    def evaluate(self, state, gradient=True):
        aggregate, derivative, local = self.measure(state.density, gradient)
        tolerance = self.settings["limit"]*self.reference_tolerance
        return ResponseValue(aggregate-1, derivative,
                             reported={"length_scale_peak_ratio": float(local.max())/tolerance,
                                       "length_scale_tolerance": tolerance})
