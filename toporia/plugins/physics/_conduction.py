# plugins/physics/_conduction.py — what 2-D and 3-D steady heat conduction share.
#
# Steady conduction with a heat source Q (W per unit area or volume) and a
# conductivity k(ρ) that follows the density:
#
#     −∇·(k ∇T) = Q      in the domain,    T = 0 on the supports (heat sinks)
#
# Discretised with one temperature per node, K(ρ) T = q, where
#
#     K = Σ_e k(ρ_e) K_e        K_e = ∫ ∇Nᵀ ∇N dV   (at unit conductivity)
#     q = Σ_e Q · V_e / n_nodes  (+ the scenario's point loads)
#
# The heat input q does not depend on the density, so the thermal compliance
# C = qᵀT is self-adjoint like the structural one:
#
#     dC/dρ_e = −dk/dρ_e · T_eᵀ K_e T_e
#
# Mapping of a Scenario onto heat conduction (the same geometry, other meaning):
#
#     supports (edge / point constraints, any dof)   fixed temperature T = 0
#     point loads and load holes                     heat input; only the load case's
#                                                    Fmag is used (the direction means nothing)
#     load objects (explicit GUI regions)            heat input of their force's magnitude
#     E0, Emin                                       conductivity of solid and of void
#     the physics parameter `heat_source`            uniform generation over the whole domain
#
# The 2-D engine (q4_heat.py) and the 3-D one (h8_heat.py) differ only in the
# element matrix, the element numbering and how a node mask is read; both are
# built on the class below, which does the assembly, the solve and the
# answers to the Physics interface.
#
# Reference: M. P. Bendsøe, O. Sigmund, Topology Optimization: Theory, Methods
# and Applications, Springer 2003, section 1.5; A. Gersborg-Hansen, M. P.
# Bendsøe, O. Sigmund, "Topology optimization of heat conduction problems using
# the finite volume method", Struct. Multidisc. Optim. 31 (2006) 251-259.

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu

from toporia.framework.params import Param
from toporia.framework.parts.physics import THERMAL_ENERGY, Physics
from toporia.framework.problem.regions import heat_inputs, validate_field
from toporia.plugins.interpolations.simp import SIMP

HEAT_SOURCE = Param(
    "heat_source", 1e-4, "Heat generation",
    "Heat generated per unit area (per unit volume in 3-D), uniformly over the whole domain, "
    "also where the design is void. The default makes qL² = 1 on a 100 mm plate with unit conductivity, "
    "the unit-square benchmark.",
    min=0.0, max=1e6, step=1e-4, decimals=6,
    source="Uniform volumetric heat generation, the loading of the heat-sink problem in Bendsøe & "
           "Sigmund, Topology Optimization (2003), section 1.5, and Gersborg-Hansen et al., "
           "Struct. Multidisc. Optim. 31 (2006) 251-259.",
)


class ConductionSolution:
    """Everything one solve produces: the state the heat engines hand to responses.

    density       : the physical density the state was solved for
    conductivity  : k(ρ) per element, flattened in the engine's element order
    T             : (n_nodes, n_load_cases) temperatures
    solve_free    : solves K_ff x = b again with the same factorisation
    weights       : one per load case
    energies      : per load case, T_eᵀ K_e T_e as a field shaped like the density
    compliances   : per load case, qᵀT
    """

    def __init__(self, density, conductivity, T, solve_free, weights, energies, compliances):
        self.density = density
        self.conductivity = conductivity
        self.T = T
        self.solve_free = solve_free
        self.weights = weights
        self.energies = energies
        self.compliances = compliances


class Conduction(Physics):
    """Steady heat conduction on a structured grid, any material law (the shared part).

    A subclass supplies the geometry through `_discretise`; this class assembles
    K(ρ), solves for every load case and answers the THERMAL_ENERGY questions.
    """

    provides = (THERMAL_ENERGY,)
    uses_interpolation = True
    params = (HEAT_SOURCE,)
    #: Order in which a density field is flattened into the element numbering: "F" or "C".
    element_order = "C"

    def _discretise(self, problem):
        """Return (KE, element_nodes, element_measure, node_ids) for the problem's grid.

        KE               element conductivity matrix at unit conductivity, (n, n)
        element_nodes    (n_elements, n) node numbers of every element
        element_measure  area (3-D: volume) of one element
        node_ids         array shaped like the node masks, holding each node's number
        """
        raise NotImplementedError

    def initialize(self, problem, settings, interpolation=None):
        scenario = problem.scenario
        self.problem = problem
        self.material = interpolation if interpolation is not None else SIMP()
        self.shape = tuple(problem.shape)
        self.heat_source = float(settings.get("heat_source", HEAT_SOURCE.default))
        self.KE, self.enodes, measure, node_ids = self._discretise(problem)
        self.n_nodes = int(node_ids.size)
        n = self.KE.shape[0]
        self.iK = np.repeat(self.enodes, n, axis=1).ravel()
        self.jK = np.tile(self.enodes, (1, n)).ravel()

        # Every support is a heat sink, whichever displacement it would have held.
        sinks = np.zeros(node_ids.shape, dtype=bool)
        for name in ("fixed_nodes", "fixed_x_nodes", "fixed_y_nodes", "fixed_z_nodes"):
            mask = getattr(problem, name, None)
            if mask is not None:
                sinks |= mask
        validate_field(problem, "temperature")
        self.fixed = np.unique(node_ids[sinks])
        self.free = np.setdiff1d(np.arange(self.n_nodes), self.fixed)
        if self.free.size == 0:
            raise ValueError("every node is a heat sink; leave part of the domain free")

        # Uniform generation: each element hands an equal share of Q·V to its nodes.
        generated = np.zeros(self.n_nodes)
        np.add.at(generated, self.enodes, self.heat_source * measure / n)
        self.forces = [(case.weight, generated + self._heat_input(index, case, node_ids))
                       for index, case in enumerate(scenario.load_cases)]

    def _heat_input(self, index, case, node_ids):
        """The heat entering at the load nodes in load case `index` (regions.heat_inputs)."""
        heat = np.zeros(self.n_nodes)
        # 3-D presets: a load is a line through the depth.  Explicit regions spread evenly.
        layers = None if hasattr(self.problem, "region_loads") else getattr(self.problem, "layer_weights", None)
        for mask, amount in heat_inputs(self.problem, index, case):
            nodes = node_ids[mask]
            if layers is not None:
                share = layers[np.nonzero(mask)[0]]
                share = share / share.sum()
            else:
                share = np.full(len(nodes), 1.0 / max(len(nodes), 1))
            np.add.at(heat, nodes, share * amount)
        return heat

    # ── Solve ─────────────────────────────────────────────────────────────────

    def solve(self, density):
        scenario = self.problem.scenario
        conductivity = self.material.stiffness(density.reshape(-1, order=self.element_order),
                                               scenario.E0, scenario.Emin)
        values = (self.KE.ravel()[None, :] * conductivity[:, None]).ravel()
        K = coo_matrix((values, (self.iK, self.jK)), shape=(self.n_nodes, self.n_nodes)).tocsc()
        solve_free = splu(K[self.free][:, self.free].tocsc()).solve
        T = np.zeros((self.n_nodes, len(self.forces)))
        energies, compliances = [], []
        for case, (_, q) in enumerate(self.forces):
            T[self.free, case] = solve_free(q[self.free])
            Te = T[self.enodes, case]
            energy = np.sum((Te @ self.KE) * Te, axis=1)
            energies.append(energy.reshape(self.shape, order=self.element_order))
            compliances.append(float(q @ T[:, case]))
        return ConductionSolution(density, conductivity, T, solve_free,
                                  [w for w, _ in self.forces], energies, compliances)

    # ── The Physics interface ─────────────────────────────────────────────────

    def stiffness_slope(self, state):
        scenario = self.problem.scenario
        return self.material.slope(state.density, scenario.E0, scenario.Emin)

    def thermal_compliance(self, state, case):
        return state.compliances[case]

    def thermal_energy(self, state, case):
        return state.energies[case]
