# methods/unstructured.py — density topology optimisation on an unstructured triangle mesh (Wave 5).
#
# The structured grid follows the axes; this method meshes the domain with triangles that
# follow its edges and round holes (plugins/physics/t3_mesh.py) and optimises one density
# per triangle, the top88 recipe on that mesh:
#
#     stiffness   E_e = Emin + ρ_e^p (E0 − Emin)                                   (SIMP)
#     solve       K(ρ) u_k = f_k with constant-strain triangles,   C = Σ_k w_k f_kᵀ u_k
#     sensitivity ∂C/∂ρ_e = −p ρ_e^{p−1} (E0 − Emin) Σ_k w_k u_ekᵀ K_e⁰ u_ek
#     filter      ρ̃_e = Σ_j H_ej A_j ρ_j / Σ_j H_ej A_j,   H_ej = max(0, r − |c_e − c_j|)
#                 (the density filter weighted by area, so a fine patch counts as much as a coarse one)
#     update      ρ ← OC: ρ_e (−∂C/∂ρ_e / (λ A_e))^½ within ±move, λ by bisection so Σ A_e ρ̃_e = V
#
# with the volume measured as area, so it does not depend on how fine the mesh is anywhere.
# The engine's record gets the triangle densities sampled on the structured grid (the one
# field every method hands over); the app shows the triangles themselves.
#
# Reference: the top88 recipe (E. Andreassen et al., SMO 43 (2011) 1-16) on a triangle mesh;
# unstructured meshes in topology optimisation as in C. Talischi, G. H. Paulino, A. Pereira,
# I. F. M. Menezes, "PolyTop", SMO 45 (2012) 329-357.

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.method import OBJECTIVE, Capabilities, OptimizationMethod


class UnstructuredDensity(OptimizationMethod):
    """SIMP density optimisation on an unstructured triangle mesh that follows edges and round holes."""

    name = "unstructured"
    label = "Density on a triangle mesh (unstructured)"
    use_when = ("When round holes or slanted edges matter: the mesh follows them instead of a staircase of squares. "
                "Compliance with the volume budget, 2-D.")
    reference = (
        "The top88 recipe (E. Andreassen et al., Struct. Multidisc. Optim. 43 (2011) 1-16) on an unstructured mesh;"
        " unstructured meshes as in C. Talischi et al., \"PolyTop\", Struct. Multidisc. Optim. 45 (2012) 329-357."
        " Papers: https://doi.org/10.1007/s00158-010-0594-7 https://doi.org/10.1007/s00158-011-0696-x"
    )
    order = 45
    capabilities = Capabilities(variable_kind="density", dims=(2,), objectives=("compliance",))
    params = (
        Param("element_size", 1.5, "Element size", "Side of the triangles, in mm.", min=0.05, max=100.0,
              step=0.25, decimals=3, units="mm"),
        Param("rmin", 3.0, "Filter radius", "Radius of the density filter, in mm.", min=0.0, max=100.0, step=0.5,
              decimals=3, units="mm"),
        Param("penal", 3.0, "SIMP penalty", "p in E = Emin + ρ^p (E0 − Emin).", min=1.0, max=6.0, step=0.5,
              decimals=2),
        Param("move", 0.2, "Move limit", "Largest change of a density in one iteration.", min=0.01, max=1.0,
              step=0.05, decimals=3),
    )

    def initialize(self, problem, solver):
        from scipy.spatial import cKDTree

        from toporia_library.physics.t3_mesh import build_mesh, element_matrices, triangle_dofs
        self.problem, s = problem, self.resolve_params(solver)
        self.settings = s
        self.mesh = mesh = build_mesh(problem, s["element_size"])
        scenario = problem.scenario
        self.E0, self.Emin = scenario.E0, scenario.Emin
        self.KE = element_matrices(mesh, scenario.nu)
        self.dofs = triangle_dofs(mesh)
        ndof = 2 * len(mesh.nodes)
        free = np.ones(ndof, bool)
        free[mesh.fixed] = False
        self.free, self.ndof = np.flatnonzero(free), ndof
        self.rows = np.repeat(self.dofs, 6, axis=1).ravel()
        self.cols = np.tile(self.dofs, (1, 6)).ravel()
        # The density filter, weighted by area.
        tree = cKDTree(mesh.centroids)
        pairs = tree.sparse_distance_matrix(tree, max(s["rmin"], 1e-12), output_type="coo_matrix")
        from scipy.sparse import coo_matrix, diags
        weight = np.maximum(0.0, s["rmin"] - pairs.data)
        H = coo_matrix((weight, (pairs.row, pairs.col)), shape=(len(mesh.areas),) * 2).tocsr()
        H = H + diags(np.where(np.asarray(H.sum(axis=1)).ravel() == 0, 1.0, 0.0))     # rmin 0: identity
        self.H = H @ diags(mesh.areas)
        self.Hs = np.asarray(self.H.sum(axis=1)).ravel()
        self.total_area = float(mesh.areas.sum())
        self.volume_limit = scenario.volfrac * problem.Lx * problem.Ly
        if float(mesh.areas[mesh.passive].sum()) > self.volume_limit:
            raise ValueError("Forced-solid material already exceeds the volume budget")
        start = min(1.0, self.volume_limit / self.total_area)
        self.x = np.where(mesh.passive, 1.0, start)
        self.physical = self._filter(self.x)
        self.change, self.compliance = np.inf, np.nan

    def _filter(self, x):
        return np.where(self.mesh.passive, 1.0, (self.H @ x) / self.Hs)

    def _solve(self, physical):
        """Compliance and its sensitivity with respect to the physical densities."""
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import spsolve
        p = self.settings["penal"]
        stiffness = self.Emin + physical ** p * (self.E0 - self.Emin)
        values = (self.KE * stiffness[:, None, None]).reshape(len(stiffness), 36).ravel()
        K = coo_matrix((values, (self.rows, self.cols)), shape=(self.ndof, self.ndof)).tocsc()
        K = ((K + K.T) * 0.5)[self.free][:, self.free]
        compliance, energy = 0.0, np.zeros_like(physical)
        for force, weight in zip(self.mesh.forces, self.mesh.weights, strict=True):
            u = np.zeros(self.ndof)
            u[self.free] = spsolve(K, force[self.free])
            ue = u[self.dofs]
            energy += weight * np.einsum("ei,eij,ej->e", ue, self.KE, ue)
            compliance += weight * float(force @ u)
        slope = p * physical ** (p - 1) * (self.E0 - self.Emin)
        return compliance, -slope * energy

    def step(self, iteration):
        self.compliance, dc_physical = self._solve(self.physical)
        # Chain rule through the filter: ∂C/∂x_j = Σ_e (∂C/∂ρ̃_e) H_ej / Hs_e.
        dc = self.H.T @ (np.where(self.mesh.passive, 0.0, dc_physical) / self.Hs)
        dv = self.H.T @ (np.where(self.mesh.passive, 0.0, self.mesh.areas) / self.Hs)
        x, move = self.x, self.settings["move"]
        active = ~self.mesh.passive
        lo, hi = 1e-12, 1e12
        for _ in range(100):
            lam = np.sqrt(lo * hi)
            new = np.clip(x * np.sqrt(np.maximum(-dc, 0.0) / (lam * np.maximum(dv, 1e-30))),
                          np.maximum(0.0, x - move), np.minimum(1.0, x + move))
            new = np.where(active, new, 1.0)
            if float(self.mesh.areas @ self._filter(new)) > self.volume_limit:
                lo = lam
            else:
                hi = lam
            if hi / lo < 1 + 1e-9:
                break
        self.change = float(np.max(np.abs(new - x)))
        self.x = new
        self.physical = self._filter(new)

    def get_density(self):
        from toporia_library.physics.t3_mesh import on_grid
        return on_grid(self.problem, self.mesh, self.physical)

    def get_responses(self):
        return {OBJECTIVE: float(self.compliance),
                "mesh_volume": float(self.mesh.areas @ self.physical) / (self.problem.Lx * self.problem.Ly),
                "triangles": float(len(self.mesh.areas))}

    def get_change(self):
        return self.change

    def mesh_view(self):
        """The triangles and their densities, for the app's view and the result (mesh.json)."""
        return {"nodes": self.mesh.nodes, "triangles": self.mesh.triangles, "values": self.physical}
