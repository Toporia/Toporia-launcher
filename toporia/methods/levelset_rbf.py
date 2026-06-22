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

from .base import OptimizationMethod, solve_fea


class LevelSetRBFMethod(OptimizationMethod):

    def initialize(self, problem, config):
        # If the mesh is too large for the dense RBF system, transparently
        # use a coarser internal mesh so "method=levelset" always runs.
        self.problem  = self._working_problem(problem, config)
        self.config   = config
        self.iteration = 0
        self.objective = np.inf
        self.change    = np.inf
        self.comp_history = []   # full compliance history (needed for convergence check)
        self.vol_history  = []

        # ── Algorithm hyper-parameters (match TOPRBF.m defaults) ─────────────
        self.nrelax = config.ls_nrelax
        self.dt     = config.ls_dt
        self.delta  = config.ls_delta
        self.mu     = config.ls_mu
        self.gamma  = config.ls_gamma
        self.lag    = 0.0    # Lagrange multiplier for volume constraint

        self._prepare_rbf()                         # build G, pGpX, pGpY, initialise Phi and Alpha
        self.density       = self._element_volume() # initial element solid fractions from Phi
        self.initial_volume = float(np.mean(self.density))

    def _working_problem(self, problem, config):
        """Reduce mesh resolution if the dense RBF matrix would be too large.

        The RBF system is nNode × nNode — memory and compute scale as O(n²).
        If the mesh has more nodes than ls_max_nodes, this creates a coarser
        internal problem so the method stays usable without manual tuning.
        """
        nnode = (problem.nelx + 1) * (problem.nely + 1)
        if nnode <= config.ls_max_nodes:
            return problem   # mesh is small enough; use as-is

        from copy import copy
        from toporia.core.problem import RectangularProblem
        cfg   = copy(config)
        # Solve for the m that gives exactly ls_max_nodes nodes: n = (Lx*m+1)(Ly*m+1) ≈ Lx*Ly*m²
        cfg.m = 0.95 * np.sqrt(config.ls_max_nodes / (config.Lx * config.Ly))
        print(f"levelset: using coarser internal mesh m={cfg.m:.3f} "
              f"because dense RBF would have {nnode} nodes")
        return RectangularProblem(cfg)

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
        if nnode > self.config.ls_max_nodes:
            raise MemoryError("Dense RBF system too large. Reduce config.m or increase ls_max_nodes.")

        x, y    = np.meshgrid(np.arange(nelx + 1), np.arange(nely + 1))
        self.X  = x; self.Y = y; self.nnode = nnode

        # Initialise Phi as signed distances to a set of seed circles placed to
        # give roughly the target volume fraction.  The bracket holes are then
        # forced solid or void according to their kind.
        r  = nely * self.config.ls_init_hole_radius
        hX = nelx * np.array([1/6,5/6,1/6,5/6,1/6,5/6,0,1/3,2/3,1,0,1/3,2/3,1,1/2])
        hY = nely * np.array([0,0,1/2,1/2,1,1,1/4,1/4,1/4,1/4,3/4,3/4,3/4,3/4,1/2])
        distances  = [np.sqrt((x-cx)**2 + (y-cy)**2) - r for cx, cy in zip(hX, hY)]
        self.Phi   = np.clip(np.minimum.reduce(distances), -3.0, 3.0)
        self._apply_bracket_holes_to_phi()

        # Build the dense RBF matrix G using the multiquadric kernel: √(r²+c²).
        c_rbf = self.config.ls_rbf_c
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

    def _apply_bracket_holes_to_phi(self):
        """Force Phi positive (solid) around fixed/load holes and negative inside voids.
        Must be called after every Phi update to maintain hole geometry."""
        px = self.X * self.problem.dx   # convert node grid indices to physical coordinates
        py = self.Y * self.problem.dy
        for hole in self.config.holes:
            dist = np.sqrt((px - hole.cx)**2 + (py - hole.cy)**2)
            if hole.kind in {"fixed", "load"}:
                self.Phi[dist <= hole.r_passive] =  3.0   # force solid around bolt ring
            self.Phi[dist <= hole.r_void] = -3.0           # force void inside hole

    def _element_volume(self):
        """Estimate the solid fraction of each element by sampling Phi on a fine grid.

        For each element a 21×21 grid of sample points is evaluated using the
        bilinear shape functions.  The fraction of points where Phi ≥ 0 (solid)
        is the element's volume fraction.
        """
        step = self.config.ls_sample_step
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

    def step(self):
        # ── 1. Compute element volumes and run FEA (penal=1: linear stiffness) ──
        self.density = self._element_volume()
        _, ce, self.objective = solve_fea(self.problem, self.config, self.density, penal=1.0)
        ele_comp = ce * (self.config.Emin + self.density * (self.config.E0 - self.config.Emin))
        vol      = float(np.mean(self.density))
        self.comp_history.append(self.objective)
        self.vol_history.append(vol)

        # ── 2. Lagrange multiplier update (volume constraint) ─────────────────
        # During the ramp phase the volume target ramps linearly from initial_volume
        # to config.volfrac over nrelax iterations.  After that, a PI-like
        # feedback law drives the volume to the target.
        if self.iteration < self.nrelax:
            self.lag = self.mu * (vol - self.initial_volume
                                  + (self.initial_volume - self.config.volfrac)
                                  * (self.iteration + 1) / self.nrelax)
        else:
            self.lag   += self.gamma * (vol - self.config.volfrac)
            self.gamma  = min(self.gamma + self.config.ls_gamma_step,
                              self.config.ls_gamma_max)

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
        self._apply_bracket_holes_to_phi()
        self.Phi = np.clip(self.Phi, -12., 12.)

        if len(self.comp_history) > 1:
            self.change = (abs(self.comp_history[-1] - self.comp_history[-2])
                           / max(abs(self.comp_history[-1]), 1.))
        self.iteration += 1

    def has_converged(self):
        """Stop when: iteration limit reached, OR both volume and compliance are stable."""
        if self.iteration >= self.config.max_iter:
            return True
        if self.iteration <= self.nrelax or len(self.comp_history) < 10:
            return False   # too early to judge convergence
        recent = np.array(self.comp_history[-10:-1])
        vol_ok  = abs(self.vol_history[-1] - self.config.volfrac) / self.config.volfrac < 1e-3
        comp_ok = np.all(np.abs(self.comp_history[-1] - recent) / max(abs(self.comp_history[-1]), 1.) < 1e-3)
        return vol_ok and comp_ok

    def get_density(self):   return self.density
    def get_objective(self): return self.objective
    def get_iteration(self): return self.iteration
