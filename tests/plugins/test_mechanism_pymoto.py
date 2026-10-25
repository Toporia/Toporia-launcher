"""Optional independent pyMOTO FE/backpropagation check of spring-loaded output."""

import importlib.util

import numpy as np
import pytest
from scipy.sparse import diags

from toporia.framework.problem.mesh import make_problem
from toporia.plugins.models.assembled import material_law
from toporia.plugins.models.pymoto_elastic import PymotoElasticModel, import_pymoto
from toporia.plugins.physics.q4_mechanism import Q4Mechanism
from toporia.plugins.problems import get_run
from toporia.plugins.responses.output_displacement import OutputDisplacement

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pymoto") is None,
                                reason="optional dependency: pip install pymoto")


def test_independent_spring_assembly_displacement_and_backpropagation_agree():
    pym = import_pymoto()
    run = get_run("Force Inverter").updated(m=0.2)
    problem = make_problem(run.scenario, run.solver.m)
    native = Q4Mechanism()
    native.initialize(problem, {}, material_law(run.solver))
    rho = np.random.default_rng(13).uniform(0.3, 0.8, problem.shape)
    response = OutputDisplacement()
    response.setup(native, problem, {key: run.scenario.objective[key] for key in ("x", "y", "angle")})
    expected = response.evaluate(native.solve(rho))

    # Different assembly, element/DOF order and automatic differentiation.
    domain = pym.VoxelDomain(problem.nelx, problem.nely, unitx=problem.dx, unity=problem.dy)
    adapter = PymotoElasticModel()
    adapter.problem = problem
    forces, _ = adapter._load_cases(domain)
    spring_diagonal = np.zeros(domain.nnodes * 2)
    for spring in run.scenario.point_springs:
        ix, iy = round(spring.x / problem.dx), round(spring.y / problem.dy)
        node = domain.get_nodenumber(ix, iy)
        spring_diagonal[domain.get_dofnumber(node, int(spring.dof == "y"), 2)] += spring.stiffness
    # J = +u_x at the right port, equivalent to maximising leftward output.
    port = domain.get_nodenumber(problem.nelx, problem.nely // 2)
    port_dof = int(domain.get_dofnumber(port, 0, 2))
    design = pym.Signal("physical_density", rho.ravel())
    load = pym.Signal("real_force", forces[:, 0])
    with pym.Network() as network:
        stiffness = pym.MathExpression(f"{run.scenario.Emin} + (1-{run.scenario.Emin})*inp0^3")(design)
        K = pym.AssembleStiffness(domain, bc=adapter._fixed_dofs(domain), e_modulus=1.0,
                                 poisson_ratio=run.scenario.nu, plane="stress",
                                 add_constant=diags(spring_diagonal, format="csc"))(stiffness)
        displacement = pym.LinSolve(solver=pym.solvers.SolverSparseLU())(K, load)
        objective = pym.EinSum("i->")(displacement[port_dof:port_dof + 1])
    network.response()
    assert float(objective.state) == pytest.approx(expected.value, rel=2e-10, abs=1e-13)
    network.reset()
    objective.sensitivity = 1.0
    network.sensitivity()
    np.testing.assert_allclose(design.sensitivity.reshape(problem.shape), expected.gradient,
                               rtol=2e-9, atol=1e-12)
