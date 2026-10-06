# methods/levelset_rbf.py — RBF level-set topology optimisation
#
# Algorithm overview:
#
#   Where the density method assigns a density 0–1 to every element, the
#   level-set method instead defines a scalar field Φ (phi) over the nodes.
#     Φ > 0  →  solid material
#     Φ < 0  →  void
#     Φ = 0  →  the structural boundary (the "level set")
#
#   Rather than storing Φ at every node independently, the field is
#   PARAMETERISED by a set of Radial Basis Function (RBF) coefficients α:
#       Φ = G × α
#   where G is a matrix of RBF kernel values between all node pairs.
#   Updating α updates the entire Φ field simultaneously, with built-in
#   smoothness — there are no isolated floating patches of material.
#
#   Each iteration:
#     1. Sample Φ to compute element volumes (how much of each element is solid)
#     2. FEA with those volumes → compliance and sensitivity
#     3. Update α in the direction that reduces compliance, subject to a
#        volume constraint enforced by a Lagrange multiplier (lag)
#
#   The method is faithful to TOPRBF.m (Luo et al.) and intentionally uses
#   dense matrix operations to match the MATLAB reference.  This means it is
#   SLOW for large meshes — use density method for m > 1.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.method import OBJECTIVE, Capabilities, OptimizationMethod
from toporia.plugins.physics.q4_plane_stress import solve_fea


class LevelSetRBFMethod(OptimizationMethod):
    """RBF level-set topology optimisation (Wang & Wang 2006; TOPRBF.m by Luo et al.), a whole method."""

    name = "levelset"
    label = "RBF level set"
    order = 30
    params = (
        Param("dt", 0.5, "Step size",
              "Evolution step for the level-set update. Larger moves the boundary faster; smaller is steadier.",
              min=0.001, max=2.0, step=0.05, decimals=3),
        Param("nrelax", 30, "Relax iters",
              "Early iterations that ramp the volume toward the target before feedback control starts.",
              min=1, max=500),
        Param("delta", 10.0, "Delta band",
              "Half-width of the smooth Dirac-delta band around Phi=0. Larger updates a wider region.",
              min=0.1, max=100.0, step=1.0, decimals=2),
        Param("mu", 20.0, "Volume penalty",
              "Volume penalty during relaxation. Higher pushes the volume toward the target harder.",
              min=0.0, max=500.0, step=1.0, decimals=2),
        Param("gamma", 0.05, "Gamma",
              "Initial feedback gain for volume correction after relaxation. Higher reacts faster but can oscillate.",
              min=0.0, max=20.0, step=0.05, decimals=3),
        Param("gamma_step", 0.05, "Gamma step",
              "Amount added to gamma each feedback iteration, until it reaches Gamma max.",
              min=0.0, max=20.0, step=0.05, decimals=3),
        Param("gamma_max", 5.0, "Gamma max",
              "Upper limit on the feedback gain, so volume correction cannot become too aggressive.",
              min=0.0, max=100.0, step=0.5, decimals=2),
        Param("init_hole_radius", 0.1, "Initial hole r",
              "Radius of the seed holes, as a fraction of the mesh height. Sets the starting topology.",
              min=0.01, max=0.5, step=0.01, decimals=3),
        Param("rbf_c", 1e-4, "RBF c",
              "Regularisation constant of the multiquadric RBF kernel. Change only if the RBF system is ill-conditioned.",
              min=1e-8, max=1e-1, step=1e-4, decimals=6),
        Param("sample_step", 0.1, "Sample step",
              "Sampling spacing used to estimate the solid fraction of each element. Smaller is more accurate but slower.",
              min=0.05, max=0.5, step=0.05, decimals=2),
        Param("max_nodes", 3000, "Max RBF nodes",
              "Node count above which the method uses a coarser internal mesh to avoid a huge dense matrix.",
              min=100, max=50000),
    )
    capabilities = Capabilities(variable_kind="level_set", accepts_filters=False)

    def initialize(self, problem, solver):
        self.settings = self.resolve_params(solver)   # this method's Param values

        # If the mesh is too large for the dense RBF system, transparently
        # use a coarser internal mesh so "method=levelset" always runs.
        self.problem  = self._working_problem(problem)
        self.solver   = solver
        self.scenario = self.problem.scenario
        self.iteration = 0
        self.objective = np.inf
        self.change    = np.inf
        self.comp_history = []   # full compliance history (needed for convergence check)
        self.vol_history  = []

        # ── Algorithm hyper-parameters (match TOPRBF.m defaults) ─────────────
        self.nrelax = self.settings["nrelax"]
        self.dt     = self.settings["dt"]
        self.delta  = self.settings["delta"]
        self.mu     = self.settings["mu"]
        self.gamma  = self.settings["gamma"]
        self.lag    = 0.0    # Lagrange multiplier for volume constraint

        self._prepare_rbf()                         # build G, pGpX, pGpY, initialise Phi and Alpha
        self.density       = self._element_volume() # initial element solid fractions from Phi
        self.initial_volume = float(np.mean(self.density))

    def _working_problem(self, problem):
        """Reduce mesh resolution if the dense RBF matrix would be too large.

        The RBF system is nNode × nNode — memory and compute scale as O(n²).
        If the mesh has more nodes than max_nodes, this builds a coarser
        internal problem from the same scenario, so the method stays usable
        without manual tuning.
        """
        nnode = (problem.nelx + 1) * (problem.nely + 1)
        if nnode <= self.settings["max_nodes"]:
            return problem   # mesh is small enough; use as-is

        from toporia.framework.problem.mesh import RectangularProblem
        # Solve for the m that gives about max_nodes nodes: n = (Lx*m+1)(Ly*m+1) ≈ Lx*Ly*m²
        m = 0.95 * np.sqrt(self.settings["max_nodes"] / (problem.Lx * problem.Ly))
        print(f"levelset: using coarser internal mesh m={m:.3f} "
              f"because dense RBF would have {nnode} nodes")
        return RectangularProblem(problem.scenario, m)

    def _prepare_rbf(self):
        """Build the RBF interpolation system and initialise the level-set field Phi.

        G is the (nNode+3) × (nNode+3) augmented RBF matrix including linear polynomial
        terms (1, x, y) to ensure the interpolation reproduces linear fields exactly.
        pGpX and pGpY are the spatial derivatives of G needed for computing |∇Φ|.

        Alpha = G⁻¹ × [Phi; 0; 0; 0] are the RBF coefficients.
        Phi is re-evaluated from Alpha each iteration via Phi = G[:-3,:] × Alpha.
        """
        nelx, nely = self.problem.nelx, self.problem.nely
        nnode = (nelx + 1) * (nely + 1)
        if nnode > self.settings["max_nodes"]:
            raise MemoryError("Dense RBF system too large. Reduce solver.m or increase method.max_nodes.")

        x, y    = np.meshgrid(np.arange(nelx + 1), np.arange(nely + 1))
        self.X  = x; self.Y = y; self.nnode = nnode

        # Initialise Phi as signed distances to a set of seed circles placed to
        # give roughly the target volume fraction.  The bracket holes are then
        # forced solid or void according to their kind.
        r  = nely * self.settings["init_hole_radius"]
        hX = nelx * np.array([1/6,5/6,1/6,5/6,1/6,5/6,0,1/3,2/3,1,0,1/3,2/3,1,1/2])
        hY = nely * np.array([0,0,1/2,1/2,1,1,1/4,1/4,1/4,1/4,3/4,3/4,3/4,3/4,1/2])
        distances  = [np.sqrt((x-cx)**2 + (y-cy)**2) - r for cx, cy in zip(hX, hY)]
        self.Phi   = np.clip(np.minimum.reduce(distances), -3.0, 3.0)
        self._apply_enforced_regions_to_phi()

        # Build the dense RBF matrix G using the multiquadric kernel: √(r²+c²).
        c_rbf = self.settings["rbf_c"]
        xv    = x.reshape(-1, order="F"); yv = y.reshape(-1, order="F")
        Ax    = xv[:, None] - xv[None, :]
        Ay    = yv[:, None] - yv[None, :]
        A     = np.sqrt(Ax**2 + Ay**2 + c_rbf**2)   # nNode × nNode RBF values

        # Augment with polynomial columns/rows (1, x, y) for linear completeness.
        self.G = np.block([
            [A,                  np.ones((nnode,1)), xv[:,None], yv[:,None]],
            [np.ones((1,nnode)), np.zeros((1,3))],
            [xv[None,:],         np.zeros((1,3))],
            [yv[None,:],         np.zeros((1,3))],
        ])
        # Derivatives of G w.r.t. node x and y coordinates — needed for |∇Φ|.
        self.pGpX = np.block([[Ax/A, np.tile([[0.,1.,0.]],(nnode,1))],
                               [np.tile([[0.],[1.],[0.]],(1,nnode)), np.zeros((3,3))]])
        self.pGpY = np.block([[Ay/A, np.tile([[0.,0.,1.]],(nnode,1))],
                               [np.tile([[0.],[0.],[1.]],(1,nnode)), np.zeros((3,3))]])

        rhs        = np.r_[self.Phi.reshape(-1, order="F"), 0., 0., 0.]
        self.Alpha = np.linalg.solve(self.G, rhs)   # solve for initial RBF coefficients
        self.ele_node = self._element_nodes()

    def _element_nodes(self):
        """Return (nelx×nely) × 4 array: global node indices of each element's corners."""
        nely, nelx = self.problem.nely, self.problem.nelx
        nodenrs = np.arange((nelx+1)*(nely+1)).reshape((nely+1,nelx+1), order="F")
        n1      = nodenrs[:-1, :-1].reshape(nelx*nely, order="F")
        return np.column_stack([n1, n1+nely+1, n1+nely+2, n1+1])  # CCW corner order

    @staticmethod
    def _nodes_touching(elem_mask):
        """Return the node mask covering every corner of every flagged element.

        Phi lives on nodes but passive/void are element masks, so a node is
        constrained when any element it touches is constrained.
        """
        nely, nelx = elem_mask.shape
        nodes = np.zeros((nely + 1, nelx + 1), dtype=bool)
        nodes[:-1, :-1] |= elem_mask
        nodes[:-1, 1:] |= elem_mask
        nodes[1:, :-1] |= elem_mask
        nodes[1:, 1:] |= elem_mask
        return nodes

    def _apply_enforced_regions_to_phi(self):
        """Pin Phi solid over passive elements and void over void elements.

        Must be called after every Phi update to maintain the enforced geometry.

        This reads the problem's element masks rather than re-rasterising
        config.holes, which means the level-set now honours enforced_areas and
        every hole kind exactly as the density methods do.  Previously it
        re-derived circles from the config and silently ignored polygons.
        """
        self.Phi[self._nodes_touching(self.problem.passive_elements)] = 3.0
        self.Phi[self._nodes_touching(self.problem.void_elements)] = -3.0

    def _element_volume(self):
        """Estimate the solid fraction of each element by sampling Phi on a fine grid.

        For each element a 21×21 grid of sample points is evaluated using the
        bilinear shape functions.  The fraction of points where Phi ≥ 0 (solid)
        is the element's volume fraction.
        """
        step = self.settings["sample_step"]
        s, t = np.meshgrid(np.arange(-1., 1.0 + 0.5 * step, step),
                           np.arange(-1., 1.0 + 0.5 * step, step))
        phi  = self.Phi.reshape(-1, order="F")
        # Bilinear interpolation: N1=(1-s)(1-t)/4, N2=(1+s)(1-t)/4, etc.
        tmp  = (np.outer((1-s.ravel())*(1-t.ravel())/4, phi[self.ele_node[:,0]])
              + np.outer((1+s.ravel())*(1-t.ravel())/4, phi[self.ele_node[:,1]])
              + np.outer((1+s.ravel())*(1+t.ravel())/4, phi[self.ele_node[:,2]])
              + np.outer((1-s.ravel())*(1+t.ravel())/4, phi[self.ele_node[:,3]]))
        vol  = np.mean(tmp >= 0., axis=0).reshape((self.problem.nely, self.problem.nelx), order="F")
        vol[self.problem.passive_elements] = 1.0
        vol[self.problem.void_elements]    = 0.0
        return np.clip(vol, 0., 1.)

    def step(self, iteration):
        # Completed-iteration count: the relaxation ramp is written zero-based.
        self.iteration = iteration - 1
        # ── 1. Compute element volumes and run FEA (penal=1: linear stiffness) ──
        self.density = self._element_volume()
        _, ce, self.objective = solve_fea(self.problem, self.density, penal=1.0)
        ele_comp = ce * (self.scenario.Emin + self.density * (self.scenario.E0 - self.scenario.Emin))
        vol      = float(np.mean(self.density))
        self.comp_history.append(self.objective)
        self.vol_history.append(vol)

        # ── 2. Lagrange multiplier update (volume constraint) ─────────────────
        # During the ramp phase the volume target ramps linearly from initial_volume
        # to scenario.volfrac over nrelax iterations.  After that, a PI-like
        # feedback law drives the volume to the target.
        if self.iteration < self.nrelax:
            self.lag = self.mu * (vol - self.initial_volume
                                  + (self.initial_volume - self.scenario.volfrac)
                                  * (self.iteration + 1) / self.nrelax)
        else:
            self.lag   += self.gamma * (vol - self.scenario.volfrac)
            self.gamma  = min(self.gamma + self.settings["gamma_step"],
                              self.settings["gamma_max"])

        # ── 3. Level-set evolution ────────────────────────────────────────────
        # grad_phi = |∇Φ| computed from the RBF derivatives.
        grad_phi  = np.sqrt((self.pGpX @ self.Alpha)**2 + (self.pGpY @ self.Alpha)**2)
        # Dirac delta δ(Φ): approximation that is non-zero only near the boundary.
        delta_phi = np.zeros_like(self.Phi)
        near = np.abs(self.Phi) <= self.delta
        delta_phi[near] = 0.75/self.delta * (1. - self.Phi[near]**2/self.delta**2)

        # Spread element compliance to nodes via simple bilinear averaging.
        ele_lr     = np.column_stack([ele_comp[:,0], ele_comp]) + np.column_stack([ele_comp, ele_comp[:,-1]])
        node_comp  = (np.vstack([ele_lr, ele_lr[-1,:]]) + np.vstack([ele_lr[0,:], ele_lr])) / 4.
        # B is the velocity field: compliance sensitivity minus volume Lagrange term,
        # weighted by the Dirac delta (only update near the boundary).
        B  = (node_comp.reshape(-1, order="F") / (np.mean(node_comp) + 1e-12) - self.lag)
        B *= delta_phi.reshape(-1, order="F") * self.delta / 0.75

        # Solve for the Alpha update: G × ΔAlpha = B
        self.Alpha += self.dt * np.linalg.solve(self.G, np.r_[B, 0., 0., 0.])

        # Re-normalise Alpha by the mean gradient magnitude at mixed elements to
        # keep the level-set field from becoming too flat or too steep.
        mixed = np.where((self.density.reshape(-1, order="F") < 1.) &
                          (self.density.reshape(-1, order="F") > 0.))[0]
        if mixed.size:
            scale_nodes = np.unique(self.ele_node[mixed, :])
            scale = np.mean(grad_phi[scale_nodes])
            if np.isfinite(scale) and abs(scale) > 1e-12:
                self.Alpha /= scale

        # Reconstruct Phi from Alpha, re-impose holes, and clip to prevent blow-up.
        self.Phi = (self.G[:-3, :] @ self.Alpha).reshape(
            (self.problem.nely + 1, self.problem.nelx + 1), order="F"
        )
        self._apply_enforced_regions_to_phi()
        self.Phi = np.clip(self.Phi, -12., 12.)

        if len(self.comp_history) > 1:
            self.change = (abs(self.comp_history[-1] - self.comp_history[-2])
                           / max(abs(self.comp_history[-1]), 1.))

    def is_converged(self):
        """Method-specific criterion: volume on target AND compliance stable.

        This cannot be written as a single design-change scalar, which is why the
        contract keeps this escape hatch.  The engine's own `change < solver.tol`
        rule still applies in addition to this one, and the iteration limit is
        the engine's business — neither is repeated here.
        """
        if self.iteration <= self.nrelax or len(self.comp_history) < 10:
            return False   # too early to judge convergence
        recent = np.array(self.comp_history[-10:-1])
        vol_ok  = abs(self.vol_history[-1] - self.scenario.volfrac) / self.scenario.volfrac < 1e-3
        comp_ok = np.all(np.abs(self.comp_history[-1] - recent) / max(abs(self.comp_history[-1]), 1.) < 1e-3)
        return vol_ok and comp_ok

    # ── Reporting ─────────────────────────────────────────────────────────────

    def get_density(self):   return self.density
    def get_change(self):    return self.change

    def get_responses(self):
        return {
            OBJECTIVE: self.objective,
            "volume": float(self.density.mean()),
        }
