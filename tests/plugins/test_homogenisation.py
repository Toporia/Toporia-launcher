"""test_homogenisation.py — multiscale: periodic unit cells, designed materials, parts made of them (Wave 5).

Homogenisation is exact for a laminate and for a solid cell; ∂C^H/∂ρ matches finite
differences in 2-D and 3-D; a maximum-bulk-modulus cell comes close to the Hashin–Shtrikman
upper bound without exceeding it; the auxetic objective gives a negative Poisson's ratio with
a stiff cell; the material card writes the homogenised matrix; and the anisotropic macro
engine reproduces the isotropic Q4 exactly for an isotropic matrix.
"""

import json
from dataclasses import replace

import numpy as np
import pytest

from toporia_core.engine.loop import initialized_method, run_single
from toporia_core.framework import Scenario, Solver
from toporia_core.framework.problem.mesh import make_problem
from toporia_core.framework.problem.run import Run
from toporia_library.interpolations.simp import SIMP
from toporia_library.physics.h8_solid import elasticity_matrix
from toporia_library.physics.homogenisation import H8PeriodicCell, Q4PeriodicCell
from toporia_library.problems import get_run


def _cell(engine_cls, scenario, m, penal=3.0):
    problem = make_problem(scenario, m)
    engine = engine_cls()
    engine.initialize(problem, {}, SIMP(penal))
    return engine, problem


def test_a_laminate_has_its_exact_moduli():
    # Layers normal to y, E = 1 and E = 0.1, ν = 0: Voigt along the layers, Reuss across and in shear
    # (exact up to the void stiffness Emin = 1e-9 the material law adds).
    engine, problem = _cell(Q4PeriodicCell, Scenario(Lx=10.0, Ly=10.0, nu=0.0), 2.0, penal=1.0)
    density = np.ones(problem.shape)
    density[: problem.shape[0] // 2] = 0.1
    C = engine.homogenised(engine.solve(density))
    reuss = 1 / (0.5 / 1.0 + 0.5 / 0.1)
    assert C[0, 0] == pytest.approx(0.55, rel=1e-8)
    assert C[1, 1] == pytest.approx(reuss, rel=1e-8) and C[2, 2] == pytest.approx(reuss / 2, rel=1e-8)
    assert abs(C[0, 1]) < 1e-12


def test_a_solid_cell_is_the_solid_material():
    engine, problem = _cell(H8PeriodicCell, Scenario(Lx=4.0, Ly=4.0, Lz=4.0, nu=0.3), 1.0)
    assert np.allclose(engine.homogenised(engine.solve(np.ones(problem.shape))), elasticity_matrix(1.0, 0.3))
    engine, problem = _cell(Q4PeriodicCell, Scenario(Lx=4.0, Ly=4.0, nu=0.3), 1.0)
    D = np.array([[1, 0.3, 0], [0.3, 1, 0], [0, 0, 0.35]]) / 0.91
    assert np.allclose(engine.homogenised(engine.solve(np.ones(problem.shape))), D)


@pytest.mark.parametrize("engine_cls, scenario, m", [
    (Q4PeriodicCell, Scenario(Lx=8.0, Ly=8.0), 1.0),
    (H8PeriodicCell, Scenario(Lx=4.0, Ly=4.0, Lz=4.0), 1.0),
])
def test_the_homogenised_sensitivity_is_exact(engine_cls, scenario, m):
    engine, problem = _cell(engine_cls, scenario, m)
    rho = np.random.default_rng(4).uniform(0.3, 0.9, problem.shape)
    state = engine.solve(rho)
    for i, j in ((0, 0), (0, 1), (len(state.C) - 1, len(state.C) - 1)):
        slope = engine.homogenised_slope(state, i, j)
        for e in np.argsort(-np.abs(slope).ravel())[:2]:
            index = np.unravel_index(e, problem.shape)
            up, down = rho.copy(), rho.copy()
            up[index] += 1e-5
            down[index] -= 1e-5
            fd = (engine.homogenised(engine.solve(up))[i, j] - engine.homogenised(engine.solve(down))[i, j]) / 2e-5
            assert slope[index] == pytest.approx(fd, rel=1e-4, abs=1e-10)


def _hashin_shtrikman_2d(f, E=1.0, nu=0.3):
    k, mu = E / (2 * (1 - nu)), E / (2 * (1 + nu))
    return k + (1 - f) / (-1 / k + f / (k + mu))


def test_a_bulk_modulus_cell_comes_close_to_the_hashin_shtrikman_bound():
    run = get_run("Material: Maximum Bulk Modulus")
    run = replace(run, scenario=replace(run.scenario, Lx=36.0, Ly=36.0),
                  solver=replace(run.solver, max_iter=250, schedules=[dict(run.solver.schedules[0], every=40)]))
    method = initialized_method(run)
    for i in range(1, 251):
        method.step(i)
    bulk, bound = method.get_responses()["bulk_modulus"], _hashin_shtrikman_2d(0.5)
    assert 0.9 * bound < bulk <= bound
    assert np.mean(method.get_density()) == pytest.approx(0.5, abs=5e-3)


def test_an_auxetic_cell_has_a_negative_poissons_ratio_and_stays_stiff():
    run = get_run("Material: Auxetic (Negative Poisson's Ratio)")
    run = replace(run, scenario=replace(run.scenario, Lx=36.0, Ly=36.0), solver=replace(run.solver, max_iter=200))
    method = initialized_method(run)
    for i in range(1, 201):
        method.step(i)
    responses = method.get_responses()
    assert responses["poisson_ratio"] < -0.3 and responses["C11"] > 0.02


def test_the_material_card_and_a_part_made_of_the_material(tmp_path):
    scenario = Scenario(Lx=20.0, Ly=20.0, volfrac=0.5, objective={"type": "bulk_modulus"})
    solver = Solver(method="q4_periodic+oc", representation={"type": "element_density", "start": "hole"},
                    filter_specs=[{"type": "density", "rmin": 2.0}], m=1.0, max_iter=15, tol=0.0)
    from toporia_core.framework.problem.run import Output
    run = Run(scenario=scenario, solver=solver, output=Output(dir=tmp_path, save_every=0,
                                                              postprocess=[{"type": "material_card"}]))
    run_single(run)
    card = json.loads((tmp_path / "post" / "material.json").read_text())
    C = np.array(card["C"])
    assert C.shape == (3, 3) and np.allclose(C, C.T) and np.min(np.linalg.eigvalsh(C)) > 0
    assert card["bulk_modulus"] == pytest.approx((C[0, 0] + C[1, 1] + 2 * C[0, 1]) / 4)
    # The card's settings build a part.
    part = get_run("Cantilever").updated(method="q4_anisotropic+oc", max_iter=3, tol=0.0)
    part = replace(part, solver=replace(part.solver, method_params=card["q4_anisotropic"]))
    method = initialized_method(part)
    method.step(1)
    assert np.isfinite(method.get_responses()["objective"])


def test_an_isotropic_matrix_reproduces_the_isotropic_engine():
    run = get_run("MBB Beam")
    iso = initialized_method(run.updated(method="q4+oc", max_iter=1))._model
    ani = initialized_method(run.updated(method="q4_anisotropic+oc", max_iter=1))._model
    x = np.random.default_rng(1).uniform(0.3, 0.9, iso.problem.shape)
    assert ani.evaluate(x, gradients=False).objective == pytest.approx(iso.evaluate(x, gradients=False).objective,
                                                                       rel=1e-12)
    with pytest.raises(ValueError, match="positive definite"):
        initialized_method(replace(run.updated(method="q4_anisotropic+oc"), solver=replace(
            run.updated(method="q4_anisotropic+oc").solver, method_params={"C12": 5.0})))
