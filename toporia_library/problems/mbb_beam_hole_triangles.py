# plugins/problems/mbb_beam_hole_triangles.py — the MBB beam with a round hole, on triangles.
#
# The MBB beam's scenario with a round hole of radius 4 mm in the middle, solved on an
# unstructured triangle mesh (methods/unstructured.py) that follows the hole's rim instead of
# cutting it into a staircase of squares.  A demonstration of unstructured meshes (Wave 5).

from dataclasses import replace

from toporia_core.framework import HoleConfig, Solver

from . import mbb_beam

NAME = "MBB Beam with a Hole (Triangles)"
ORDER = 20
ABOUT = ("The MBB beam with a round hole, optimised on a triangle mesh that follows the hole's rim instead of a"
         " staircase of squares.")
REFERENCE = ('The top88 recipe on an unstructured mesh; unstructured meshes in topology optimisation as in'
             ' C. Talischi, G. H. Paulino, A. Pereira, I. F. M. Menezes, "PolyTop", Struct. Multidisc. Optim. 45'
             " (2012) 329-357. Demonstration preset. Papers: https://doi.org/10.1007/s00158-011-0696-x")


def scenario():
    """The MBB beam with a round hole of radius 4 mm at its centre."""
    return replace(mbb_beam.scenario(), holes=[HoleConfig(cx=30.0, cy=10.0, r_void=4.0, r_passive=4.0)])


def solver() -> Solver:
    """Density on 1.5 mm triangles, a 3 mm filter, SIMP p = 3, OC."""
    return Solver(method="unstructured", method_params={"element_size": 1.5, "rmin": 3.0},
                  filter_specs=[], m=1.0, max_iter=200, tol=0.01)


def _description():
    from ._research import Equation, ResearchDescription
    module = __import__(__name__, fromlist=["x"])
    return ResearchDescription(
        question=ABOUT,
        setup=("60 x 20 mm half-MBB beam with a round hole of radius 4 mm at (30, 10); triangles of about 1.5 mm "
               "(a near-equilateral lattice, the edges and the hole's rim sampled every 1.5 mm, Delaunay); SIMP p = 3, "
               "area-weighted density filter of radius 3 mm, OC with move 0.2, volume fraction 0.5 by area."),
        computes=("Each iteration solves constant-strain triangles, takes the compliance sensitivity per triangle, "
                  "filters it and updates the densities by optimality criteria with the volume measured as area."),
        equations=(
            Equation(r"K_e=A_e\,t\,B_e^{\mathsf{T}}DB_e,\quad E_e=E_{\min}+\tilde\rho_e^{\,p}(E_0-E_{\min})",
                     "Constant-strain triangles: B_e is constant on each triangle, so the element matrix is the area "
                     "times one product; SIMP scales it."),
            Equation(r"\tilde\rho_e=\frac{\sum_j H_{ej}A_j\rho_j}{\sum_j H_{ej}A_j},\quad H_{ej}=\max(0,r-|c_e-c_j|)",
                     "The density filter weighted by area, so a fine part of the mesh does not count more."),
            Equation(r"\frac{\partial C}{\partial\tilde\rho_e}=-p\,\tilde\rho_e^{\,p-1}(E_0-E_{\min})\sum_k w_k u_{ek}^{"
                     r"\mathsf{T}}K_e^0u_{ek}",
                     "Self-adjoint compliance sensitivity; the filter's adjoint carries it to the design variables."),
        ),
        symbols=("A_e: triangle area; t: thickness; B_e: strain-displacement matrix; D: plane-stress matrix; rho: "
                 "density, tilde: filtered; c_e: triangle centroid; r: filter radius; p: SIMP penalty; u_ek: element "
                 "displacements in load case k with weight w_k; K_e^0: element matrix at unit stiffness."),
        source_url="https://doi.org/10.1007/s00158-011-0696-x",
        figure="A half-MBB beam layout around a round hole.",
        comparison="Compare with the MBB beam on the structured grid with the same hole: the hole's rim is smooth here.",
        limitations="2-D only; constant-strain triangles are stiffer than Q4 at the same size; uniform element size.",
        reproduce=f'toporia run "{NAME}"',
        functions=("method:unstructured", "response:compliance"),
    ) if module else None
