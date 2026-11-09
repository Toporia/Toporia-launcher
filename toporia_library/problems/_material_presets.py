# toporia_library/problems/_material_presets.py — shared parts of the microstructure presets (multiscale).

from toporia_core.framework import Scenario, Solver
from toporia_core.framework.problem.run import Output

from ._research import Equation, ResearchDescription

EQUATIONS = (
    Equation(r"K(\rho)\chi^i=f^i,\quad f^i=\sum_e K_e(\rho_e)\,u^{0i}_e",
             "For each unit test strain i, the periodic cell is solved for its fluctuation chi (opposite faces are "
             "the same nodes, one node is held)."),
    Equation(r"C^H_{ij}=\frac{1}{|Y|}\sum_e E(\rho_e)\,(u^{0i}-\chi^i)_e^{\mathsf{T}}K_e^0(u^{0j}-\chi^j)_e",
             "The homogenised elasticity matrix, in energy form: the stiffness of a large piece of the material."),
    Equation(r"\frac{\partial C^H_{ij}}{\partial\rho_e}=\frac{1}{|Y|}E'(\rho_e)\,(u^{0i}-\chi^i)_e^{\mathsf{T}}"
             r"K_e^0(u^{0j}-\chi^j)_e",
             "Exact sensitivity without an adjoint solve: the energy is stationary in chi."),
)


def cell(size, volfrac, objective, depth=0.0):
    """A square (cubic) unit cell of `size` mm."""
    return Scenario(Lx=size, Ly=size, Lz=depth, volfrac=volfrac, nu=0.3, objective=objective)


def projected_solver(model, rmin, iterations, every=50, end=32.0):
    """MMA on element densities started with a hole, a density filter and a sharpening Heaviside projection."""
    return Solver(method=f"{model}+mma", representation={"type": "element_density", "start": "hole"},
                  filter_specs=[{"type": "density", "rmin": rmin}, {"type": "heaviside", "beta": 1.0}],
                  schedules=[{"path": "filters[1].beta", "type": "geometric", "start": 1.0, "end": end,
                              "factor": 2.0, "every": every}],
                  m=1.0, max_iter=iterations, tol=0.0)


def card():
    """At the end: the material card (homogenised matrix and the q4_anisotropic settings)."""
    return Output(postprocess=[{"type": "material_card"}])


def description(module, computes, comparison):
    """The research description of a microstructure preset."""
    solver = module.solver()
    scenario = module.scenario()
    dims = "3-D" if scenario.Lz else "2-D"
    return ResearchDescription(
        question=module.ABOUT,
        setup=(f"A {dims} periodic unit cell of {scenario.Lx:g} mm, volume fraction {scenario.volfrac:g}, E0 = 1, "
               f"nu = 0.3; {solver.method}, filters {[spec['type'] for spec in solver.filter_specs]}, started from a "
               f"cell with a hole in the middle."),
        computes=computes,
        equations=EQUATIONS,
        symbols=("chi^i: periodic fluctuation for test strain i; u^0i: displacements of the uniform test strain; "
                 "K_e: element matrix, K_e^0 at unit stiffness; E(rho): the material law; |Y|: cell size; C^H: "
                 "homogenised elasticity matrix (Voigt)."),
        source_url="https://doi.org/10.1007/s00158-015-1294-0",
        figure="A periodic material microstructure.",
        comparison=comparison,
        limitations=("Linear elasticity, small strains, one length scale (the cell is much smaller than the part); "
                     "the optimum depends on the start design and the filter radius."),
        reproduce=f'toporia run "{module.NAME}"',
        functions=(f"model:{solver.method.split('+')[0]}", "updater:mma",
                   *[f"filter:{spec['type']}" for spec in solver.filter_specs],
                   f"response:{scenario.objective['type']}", "postprocessor:material_card"),
    )
