# toporia_library/problems/_unstructured_description.py — the research description of the tetrahedral presets.

from ._research import Equation, ResearchDescription

EQUATIONS = (
    Equation(r"p\leftarrow p-\frac{\phi(p)\,\nabla\phi(p)}{|\nabla\phi(p)|^2}",
             "Nodes near a void surface are moved onto it (phi < 0 inside the void) by Newton steps; a move that "
             "would invert or flatten a tetrahedron is undone."),
    Equation(r"K_e=V_e\,B_e^{\mathsf{T}}DB_e,\quad E_e=E_{\min}+\tilde\rho_e^{\,p}(E_0-E_{\min})",
             "Linear tetrahedra: B_e is constant on each tetrahedron, so the element matrix is its volume times "
             "one product; SIMP scales it."),
    Equation(r"\tilde\rho_e=\frac{\sum_j H_{ej}V_j\rho_j}{\sum_j H_{ej}V_j},\quad H_{ej}=\max(0,r-|c_e-c_j|)",
             "The density filter weighted by volume, so a finely meshed region does not count more."),
    Equation(r"\frac{\partial C}{\partial\tilde\rho_e}=-p\,\tilde\rho_e^{\,p-1}(E_0-E_{\min})\sum_k w_k "
             r"u_{ek}^{\mathsf{T}}K_e^0u_{ek}",
             "Self-adjoint compliance sensitivity; the filter's adjoint carries it to the design variables."),
)


def unstructured_description(module):
    """The description of a preset solved on tetrahedra."""
    params = module.solver().method_params
    return ResearchDescription(
        question=module.ABOUT,
        setup=(f"Tetrahedra from cubes of about {params.get('element_size', 2.0)} mm split in six (Kuhn), nodes "
               f"snapped onto the voids; SIMP p = 3, volume-weighted density filter of radius "
               f"{params.get('rmin', 4.0)} mm, OC with move 0.2, the volume budget measured as volume."),
        computes=("Each iteration solves linear tetrahedra, takes the compliance sensitivity per tetrahedron, "
                  "filters it and updates the densities by optimality criteria; at the end the boundary of the "
                  "solid tetrahedra is written as an STL that follows the voids."),
        equations=EQUATIONS,
        symbols=("p: a node; phi: the void's implicit function, negative inside; V_e: tetrahedron volume; B_e: "
                 "strain-displacement matrix; D: 3-D elasticity matrix; rho: density, tilde: filtered; c_e: "
                 "centroid; r: filter radius; u_ek: element displacements in load case k with weight w_k; K_e^0: "
                 "element matrix at unit stiffness."),
        source_url="https://doi.org/10.1007/s00158-014-1107-x",
        figure="A 3-D layout around a round void.",
        comparison=("The tetrahedra are checked against Timoshenko beam theory and their volume converges to the "
                    "exact domain volume at second order in the element size (tests/plugins/test_tetrahedra.py)."),
        limitations=("Linear tetrahedra are stiffer than bricks at the same size (they converge from above); "
                     "voids with an implicit function (holes through the depth, spheres, cylinders, boxes) are "
                     "followed, other void shapes are cut along the structured grid."),
        reproduce=f'toporia run "{module.NAME}"',
        functions=("method:unstructured", "response:compliance", "postprocessor:mesh_surface"),
    )
