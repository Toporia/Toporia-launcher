# plugins/physics/truss_nodes.py — what happens at the nodes of a truss.  TOPORIA'S OWN.
#
# The ground-structure literature (Dorn, Gomory & Greenberg 1964 and after) treats a node as
# an ideal pin: a point where bars meet, with no size, mass or stiffness of its own.  That is
# the default here too.  The two node models below are Toporia's own additions, not taken
# from a paper; they are marked as such in the catalogue (toporia_library/LIBRARY.md).
#
#   pin       the classic node: connects bars, adds nothing
#   joint     a joint with material: every bar end brings a joint length ℓ of its own cross-
#             section into the node, so a joint where heavy bars meet is big.  It counts in the
#             volume and the mass:
#                 volume  Σ_i a_i (L_i + 2ℓ)          (instead of Σ a_i L_i)
#                 mass    m_n = ρ Σ_{i at n} a_i (L_i/2 + ℓ)   lumped at node n
#             so it changes what the volume budget allows and lowers natural frequencies.  The
#             solid post-processor draws it as a ball of the same volume:
#                 2-D  π R² = ℓ Σ a_i,     3-D  (4/3) π R³ = ℓ Σ a_i
#   anchor    a node tied to where it started by a spring of stiffness k on every axis, K_nn += k I:
#             a flexible mounting.  Nodes inside a spring object of the Problem page are anchored
#             with that object's stiffness on its axes; `anchor_stiffness` anchors every free node.
#
# A node can also carry a value of your own for its view: a formula of
#     displacement   |u_n| in the first load case (or the first mode, for a frequency objective)
#     joint_area     Σ a_i of the bars meeting at n
#     force          Σ |N_i| of the bars meeting at n
#     x, y, z        its coordinates
# checked like every formula in Toporia (framework/variables.py).

import numpy as np

NODE_NAMES = ("displacement", "joint_area", "force", "x", "y", "z")


def effective_lengths(lengths, joint_length):
    """The length of material each bar puts into the structure: L_i + 2ℓ with joints, L_i with pins."""
    return lengths + 2.0 * joint_length


def joint_area(structure, areas):
    """Σ a_i of the bars meeting at every node."""
    total = np.zeros(len(structure.nodes))
    np.add.at(total, structure.bars[:, 0], areas)
    np.add.at(total, structure.bars[:, 1], areas)
    return total


def lumped_mass(structure, areas, density, joint_length):
    """The mass at every node: half of each bar meeting there, plus its joint share."""
    share = density * areas * (structure.lengths / 2.0 + joint_length)
    mass = np.zeros(len(structure.nodes))
    np.add.at(mass, structure.bars[:, 0], share)
    np.add.at(mass, structure.bars[:, 1], share)
    return mass


def mass_slope(structure, density, joint_length):
    """d(mass at each end)/d(a_i) = ρ (L_i/2 + ℓ), the same at both ends of bar i."""
    return density * (structure.lengths / 2.0 + joint_length)


def joint_radius(structure, areas, joint_length):
    """The radius of a ball holding a joint's material (0 for pin joints)."""
    volume = joint_length * joint_area(structure, areas)
    if structure.dims == 2:
        return np.sqrt(volume / np.pi)
    return np.cbrt(3.0 * volume / (4.0 * np.pi))


def anchors(problem, structure, everywhere=0.0):
    """Spring stiffness per DOF: spring objects of the Problem page on their axes, plus `everywhere` on free DOFs."""
    from toporia_library.physics.truss import node_coordinates_grid
    dims = structure.dims
    diagonal = np.zeros(structure.ndof)
    coordinates = node_coordinates_grid(problem)
    for mask, axes, stiffness in getattr(problem, "region_springs", ()):
        points = coordinates[mask]
        inside = [int(np.argmin(np.sum((structure.nodes - p) ** 2, axis=1))) for p in points]
        nodes = sorted(set(inside))
        for axis in axes:
            component = "xyz".index(axis)
            if component < dims:
                diagonal[np.array(nodes, int) * dims + component] += stiffness / max(len(nodes), 1)
    if everywhere > 0:
        free = np.ones(structure.ndof, bool)
        free[structure.fixed] = False
        diagonal[free] += everywhere
    return diagonal


def node_values(formula_text, structure, areas, displacement, forces):
    """The node formula at every node, or None when it is empty."""
    from toporia_core.framework.variables import compile_expression
    text = (formula_text or "").strip()
    if not text:
        return None
    formula = compile_expression(text, set(NODE_NAMES), what="The node value")
    dims = structure.dims
    u = np.zeros((len(structure.nodes), dims)) if displacement is None else displacement.reshape(-1, dims)
    force = np.zeros(len(structure.nodes))
    if forces is not None:
        np.add.at(force, structure.bars[:, 0], np.abs(forces))
        np.add.at(force, structure.bars[:, 1], np.abs(forces))
    columns = {"displacement": np.linalg.norm(u, axis=1), "joint_area": joint_area(structure, areas),
               "force": force, "x": structure.nodes[:, 0], "y": structure.nodes[:, 1],
               "z": structure.nodes[:, 2] if dims == 3 else np.zeros(len(structure.nodes))}
    return np.array([formula({name: float(column[n]) for name, column in columns.items()})
                     for n in range(len(structure.nodes))])
