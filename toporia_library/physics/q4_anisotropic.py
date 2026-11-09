# toporia_library/physics/q4_anisotropic.py — plane stress in a material of your own constitutive matrix.
#
# The macro half of multiscale design: a part made of a designed material.  The material's
# plane-stress elasticity matrix (Voigt: xx, yy, engineering xy)
#
#         [ C11  C12  C13 ]
#     C = [ C12  C22  C23 ]
#         [ C13  C23  C33 ]
#
# is given as parameters, typically the homogenised matrix C^H of a unit cell designed with the
# q4_periodic model (the post-processor material_card writes it ready to paste).  Every
# element's matrix is K_e = (E(ρ_e)/E0) ∫ Bᵀ C B dA (2 × 2 Gauss), so the design places that
# material and the material law penalises grey as usual; compliance and its sensitivity
# ∂C/∂ρ_e = −(E'(ρ_e)/E0) Σ_k w_k u_ekᵀ K_C u_ek are exact.  C must be positive definite.
#
# Reference: two-scale (sequential) design, as in the multiscale reviews of J. Wu, O. Sigmund,
# J. P. Groen, "Topology optimization of multi-scale structures: a review", Struct. Multidisc.
# Optim. 63 (2021) 1455-1480.

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.physics import ELASTIC_ENERGY

from .q4_orthotropic import element_matrix
from .q4_plane_stress import Q4PlaneStress


def _entry(name, default, label):
    return Param(name, default, label, f"{label} of the material's plane-stress elasticity matrix (Voigt, "
                 "engineering shear), in the scenario's stress units.", min=-1e12, max=1e12, step=0.01, decimals=6)


class Q4Anisotropic(Q4PlaneStress):
    """Plane stress in a material given by its full constitutive matrix (e.g. a designed microstructure)."""

    name = "q4_anisotropic"
    label = "2-D Q4 in a designed material (constitutive matrix)"
    order = 19
    provides = (ELASTIC_ENERGY,)
    params = (
        _entry("C11", 1.0 / 0.91, "C11"), _entry("C12", 0.3 / 0.91, "C12"), _entry("C22", 1.0 / 0.91, "C22"),
        _entry("C33", 0.35 / 0.91, "C33"), _entry("C13", 0.0, "C13"), _entry("C23", 0.0, "C23"),
    )

    @staticmethod
    def matrix(settings):
        """C from the parameters; refused unless positive definite."""
        g = settings.get
        C = np.array([[g("C11", 1 / 0.91), g("C12", 0.3 / 0.91), g("C13", 0.0)],
                      [g("C12", 0.3 / 0.91), g("C22", 1 / 0.91), g("C23", 0.0)],
                      [g("C13", 0.0), g("C23", 0.0), g("C33", 0.35 / 0.91)]], dtype=float)
        if np.min(np.linalg.eigvalsh(C)) <= 0:
            raise ValueError("The constitutive matrix must be positive definite (a real, stable material)")
        return C

    def initialize(self, problem, settings, interpolation=None):
        super().initialize(problem, settings, interpolation)
        # The material law scales by E(ρ); dividing by E0 makes a solid element exactly C.
        self.KE = element_matrix(self.matrix(settings), problem.dx, problem.dy) / problem.scenario.E0

    def solve(self, density):
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import spsolve

        from .q4_plane_stress import Q4Solution
        scenario, layout = self.problem.scenario, self.layout
        stiffness = self.material.stiffness(density.reshape(-1, order="F"), scenario.E0, scenario.Emin)
        values = (self.KE.ravel(order="F")[None, :] * stiffness[:, None]).ravel()
        rows, cols = np.tile(self.edof, (1, 8)).ravel(), np.repeat(self.edof, 8, axis=1).ravel()
        K = coo_matrix((values, (rows, cols)), shape=(layout.ndof, layout.ndof)).tocsc()
        Kff = ((K + K.T) * 0.5)[layout.free_dofs][:, layout.free_dofs]
        U = np.zeros((layout.ndof, len(layout.forces)))
        energies, compliances = [], []
        for k, (_, f) in enumerate(layout.forces):
            U[layout.free_dofs, k] = spsolve(Kff, f[layout.free_dofs])
            ue = U[self.edof, k]
            energy = np.sum((ue @ self.KE) * ue, axis=1)
            energies.append(self._field(energy))
            compliances.append(float(np.sum(stiffness * energy)))
        return Q4Solution(density, stiffness, U, Kff, [w for w, _ in layout.forces], energies, compliances)
