"""test_fe.py — unit tests for the Q4 plane-stress element.

Unlike the golden tests these assert real physics rather than "same as before",
so they stay valid across the whole restructure.
"""

import numpy as np

from toporia.library.fe.q4_plane_stress import element_stiffness

# The analytical unit-square matrix from Andreassen et al. (2011), top88.
A11 = np.array([[12, 3, -6, -3], [3, 12, 3, 0], [-6, 3, 12, -3], [-3, 0, -3, 12]])
A12 = np.array([[-6, -3, 0, 3], [-3, -6, -3, -6], [0, -3, -6, 3], [3, -6, 3, -6]])
B11 = np.array([[-4, 3, -2, 9], [3, -4, -9, 4], [-2, -9, -4, -3], [9, 4, -3, -4]])
B12 = np.array([[2, -3, 4, -9], [-3, 2, 9, -2], [4, 9, 2, 3], [-9, -2, 3, 2]])


def _top88_ke(nu):
    return (1.0 / (1.0 - nu ** 2) / 24.0
            * (np.block([[A11, A12], [A12.T, A11]]) + nu * np.block([[B11, B12], [B12.T, B11]])))


def test_reproduces_top88_reference_matrix():
    """Gauss integration must match the published closed form exactly."""
    for nu in (0.0, 0.3, 0.45):
        assert np.allclose(element_stiffness(nu), _top88_ke(nu), atol=1e-12)


def test_2d_stiffness_is_invariant_to_uniform_scaling():
    """In 2-D, B ~ 1/h and dA ~ h^2, so K does not depend on element size.

    This is why the hardcoded unit-square matrix was never wrong for the square
    meshes Toporia builds — and why a 3-D solver cannot make the same assumption.
    """
    reference = element_stiffness(0.3, 1.0, 1.0)
    for h in (0.1, 2.5, 100.0):
        assert np.allclose(element_stiffness(0.3, h, h), reference, atol=1e-12)


def test_aspect_ratio_changes_stiffness():
    """A stretched element is genuinely different — the case the old matrix missed."""
    square = element_stiffness(0.3, 1.0, 1.0)
    stretched = element_stiffness(0.3, 1.0, 2.0)
    assert not np.allclose(square, stretched, atol=1e-3)


def test_thickness_scales_linearly():
    reference = element_stiffness(0.3)
    assert np.allclose(element_stiffness(0.3, thickness=3.0), 3.0 * reference, atol=1e-12)


def test_rigid_body_modes_are_stress_free():
    """Translation and rotation must produce zero nodal force."""
    KE = element_stiffness(0.3)
    x, y = np.array([0.0, 1.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0, 1.0])
    modes = [np.column_stack([np.ones(4), np.zeros(4)]).ravel(),   # translate x
             np.column_stack([np.zeros(4), np.ones(4)]).ravel(),   # translate y
             np.column_stack([-y, x]).ravel()]                     # rotate
    for mode in modes:
        assert np.abs(KE @ mode).max() < 1e-12


def test_symmetric_and_positive_semidefinite():
    KE = element_stiffness(0.3)
    assert np.allclose(KE, KE.T, atol=1e-14)
    assert np.linalg.eigvalsh(KE).min() > -1e-12
