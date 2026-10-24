# plugins/representations/bspline.py — a density field as a B-spline of a few coefficients.
#
# The design variables are the coefficients c of a tensor-product B-spline on a
# coarse control grid; the element density is the spline evaluated at the
# element centres,
#
#     ρ(x, y) = Σ_i Σ_j  N_i(x) · M_j(y) · c_ij,
#
# with N_i, M_j the B-spline basis functions of degree p (2 or 3) on a clamped
# uniform knot vector.  Because the evaluation points are fixed, so is the
# 1-D basis matrix of each axis (Bx: nelx × n_x, By: nely × n_y, and Bz in 3-D),
# and the whole map is linear:
#
#     field = By · C · Bxᵀ      (2-D),        dC = Byᵀ · S · Bx,
#
# where S is the sensitivity with respect to the field.  The backward pass is
# just the transpose.  The basis functions are non-negative and sum to one (a
# partition of unity), so a density is a weighted mean of the coefficients near
# it: with every coefficient in [0, 1] every density is too — no clipping — and
# all-ones coefficients give an all-ones field.  The start design is every
# coefficient equal to the volume fraction, which gives that density everywhere.
#
# Why use it: the control grid, not the mesh, carries the resolution.  A field
# of n_x × n_y coefficients cannot vary faster than the grid allows, so it has a
# built-in length scale, a smooth boundary and far fewer variables than elements
# (the mesh can be refined without growing the problem).  The price is that
# features finer than the control grid cannot be drawn, and gray is not penalised
# by the representation itself — pair it with the usual material law and projection.
#
# The map is separable, so it is applied one axis at a time (never as one big
# matrix); in 3-D it needs nothing more than a third axis.
#
# Reference: X. Qian, "Topology optimization in B-spline space", Computer
# Methods in Applied Mechanics and Engineering 265 (2013) 15-35.

import numpy as np
from scipy.interpolate import BSpline

from toporia.framework.params import Param
from toporia.framework.parts.representation import Representation


def basis_matrix(n_points, n_coefficients, degree):
    """B-spline basis at the centres of `n_points` equal cells, for `n_coefficients` clamped uniform splines.

    Returns an (n_points, n_coefficients) array; each row is non-negative and sums to one.
    """
    if n_coefficients <= degree:
        raise ValueError(f"a degree-{degree} B-spline needs more than {degree} control points per axis, "
                         f"got {n_coefficients}")
    interior = np.linspace(0.0, 1.0, n_coefficients - degree + 1)[1:-1]
    knots = np.concatenate([np.zeros(degree + 1), interior, np.ones(degree + 1)])
    centres = (np.arange(n_points) + 0.5) / n_points
    return BSpline(knots, np.eye(n_coefficients), degree)(centres)


def _along_axis(matrix, field, axis):
    """Multiply `field` by `matrix` along one axis (the matrix's second index meets that axis)."""
    return np.moveaxis(np.tensordot(matrix, field, axes=(1, axis)), 0, axis)


class BSplineField(Representation):
    """The element density is a tensor-product B-spline of a coarse grid of coefficients."""

    name = "bspline"
    reference = (
        'X. Qian, "Topology optimization in B-spline space", Comput. Methods Appl. Mech. Eng. '
        '265 (2013) 15-35.'
    )
    label = "B-spline field"
    order = 30
    element_wise = False
    dims = (2, 3)
    advice = ("The coefficients live on a coarse grid, so a move limit of the usual size works "
              "(method.move 0.1 to 0.2); more control points give finer features but more variables.")
    params = (
        Param("n_x", 24, "Control points across", "Coefficients along x. More: finer features, more variables.",
              min=4, max=200),
        Param("n_y", 12, "Control points down", "Coefficients along y.", min=4, max=200),
        Param("n_z", 6, "Control points deep", "Coefficients along z (3-D problems only).", min=4, max=100),
        Param("degree", 3, "Spline degree",
              "Smoothness of the field: 2 is quadratic, 3 is cubic (smoother, wider support).",
              choices=((2, "2 (quadratic)"), (3, "3 (cubic)"))),
    )

    def __init__(self, n_x=24, n_y=12, n_z=6, degree=3):
        self.n_x, self.n_y, self.n_z = int(n_x), int(n_y), int(n_z)
        self.degree = int(degree)
        if self.degree not in (2, 3):
            raise ValueError(f"degree must be 2 or 3, not {degree!r}")

    def setup(self, problem):
        self.problem = problem
        # Control points per axis, in the order of problem.shape (z, y, x or y, x).
        counts = (self.n_z, self.n_y, self.n_x)[-len(problem.shape):]
        self.grid = counts
        self.matrices = [basis_matrix(n, c, self.degree) for n, c in zip(problem.shape, counts)]
        self._start = np.full(counts, problem.scenario.volfrac).reshape(-1)

    def initial(self):
        return self._start.copy()

    def bounds(self):
        # [0, 1] on the coefficients is what keeps every density in [0, 1].
        return np.zeros_like(self._start), np.ones_like(self._start)

    def density(self, z):
        field = np.asarray(z).reshape(self.grid)
        for axis, matrix in enumerate(self.matrices):
            field = _along_axis(matrix, field, axis)
        return field

    def backward(self, z, sensitivity):
        gradient = np.asarray(sensitivity)
        for axis, matrix in enumerate(self.matrices):
            gradient = _along_axis(matrix.T, gradient, axis)
        return gradient.reshape(-1)
