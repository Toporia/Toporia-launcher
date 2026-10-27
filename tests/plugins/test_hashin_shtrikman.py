"""Independent HS upper-channel checks, context binding and physical gradients."""

from types import SimpleNamespace

import numpy as np
import pytest

from toporia.checks import conformance
from toporia.engine.loop import initialized_method
from toporia.engine.pipeline import solver_problems
from toporia.plugins.interpolations.hashin_shtrikman import HashinShtrikman
from toporia.plugins.methods import method_class
from toporia.plugins.problems import get_run


def law_for(nu=.3, dimension=2):
    law = HashinShtrikman()
    law.setup(SimpleNamespace(shape=(2,)*dimension, scenario=SimpleNamespace(nu=nu)))
    return law


@pytest.mark.parametrize("dimension", [2, 3])
@pytest.mark.parametrize("nu", [-.5, 0., .2, .3, 1/3, .49])
@pytest.mark.parametrize("ratio", [0., 1e-9, .1, .9, 1.])
def test_matches_the_stricter_independent_bulk_and_shear_upper_bounds(dimension, nu, ratio):
    rho = np.linspace(0, 1, 51)
    law = law_for(nu, dimension)
    actual = law.stiffness(rho, 1., ratio)
    g = 1/(2*(1+nu))
    if dimension == 2:
        k = 1/(2*(1-nu))
        shifts = [g, k*g/(k+2*g)]
    else:
        k = 1/(3*(1-2*nu))
        shifts = [4*g/3, g*(9*k+8*g)/(6*(k+2*g))]
    # Reciprocal HS form, not the implementation's RAMP coefficient formula.
    upper = []
    for modulus, shift in zip([k, g], shifts, strict=True):
        bound = 1 / (rho/(modulus+shift) + (1-rho)/(ratio*modulus+shift)) - shift
        upper.append(bound/modulus)
    np.testing.assert_allclose(actual, np.minimum(*upper), rtol=3e-13, atol=3e-15)
    assert actual[0] == ratio and actual[-1] == 1.
    assert np.all(np.diff(actual) >= -1e-15)
    derivative = np.imag(law.stiffness(rho+1e-25j, 1., ratio))/1e-25
    np.testing.assert_allclose(derivative, law.slope(rho, 1., ratio), rtol=5e-15)


def test_conformance():
    conformance(HashinShtrikman).assert_ok()


def test_plane_stress_special_case_is_the_papers_young_modulus_bound():
    rho = np.linspace(0, 1, 31)
    law = law_for(1/3)
    np.testing.assert_allclose(law.stiffness(rho, 2., 0.), 2*rho/(3-2*rho), rtol=2e-15)
    # nu=.3 must satisfy both channels, not just use the special-case q=2.
    assert law_for(.3).stiffness(np.array([.5]), 1., 0.)[0] < 1/4


@pytest.mark.parametrize("dimension", [2, 3])
def test_context_uses_actual_scenario_nu_and_dimension(dimension):
    model = initialized_method(get_run("Cantilever").updated(
        method="q4+mma" if dimension == 2 else "h8+mma", m=.2, Lz=5 if dimension == 3 else 0,
        nu=.2, point_loads=[], interpolation={"type": "hashin_shtrikman"}))._model
    assert model.material.nu == .2 and model.material.dimension == dimension
    rho = np.full(model.problem.shape, .5)
    expected = law_for(.2, dimension).stiffness(rho, 1., 1e-9)
    np.testing.assert_allclose(model.engine.material.stiffness(rho, 1., 1e-9), expected)


@pytest.mark.parametrize("dimension", [2, 3])
@pytest.mark.parametrize("nu", [0., .3])
def test_filtered_compliance_adjoint_with_contextual_law(dimension, nu):
    method = initialized_method(get_run("Cantilever").updated(
        method="q4+mma" if dimension == 2 else "h8+mma", m=.2, nu=nu,
        Lz=5 if dimension == 3 else 0, point_loads=[], interpolation={"type": "hashin_shtrikman"}))
    model = method._model
    z = method.x + np.random.default_rng(4).normal(0, .03, method.x.shape)
    direction = np.random.default_rng(3).normal(size=z.shape)
    direction /= np.linalg.norm(direction)
    e = model.evaluate(z)
    a, b = model.evaluate(z+1e-4*direction), model.evaluate(z-1e-4*direction)
    assert (a.objective-b.objective)/2e-4 == pytest.approx(np.sum(e.objective_gradient*direction), rel=3e-6)
    assert e.volume == pytest.approx(model.physical(z).sum())


def test_thermal_pairings_are_refused_in_preflight_and_direct_model_initialisation():
    run = get_run("Cantilever").updated(method="q4_heat+mma", m=.2,
                                       objective={"type": "thermal_compliance"},
                                       interpolation={"type": "hashin_shtrikman"})
    assert any("elastic bulk/shear" in reason for reason in solver_problems(method_class(run.solver.method), run))
    with pytest.raises(ValueError, match="elastic bulk/shear"):
        initialized_method(run)


def test_context_is_required_for_direct_use():
    with pytest.raises(ValueError, match="setup"):
        HashinShtrikman().stiffness(np.array([.5]), 1., 1e-9)


@pytest.mark.parametrize("nu", [-1., .5, np.nan])
def test_invalid_poisson_ratio(nu):
    with pytest.raises(ValueError, match="Poisson"):
        law_for(nu)


@pytest.mark.parametrize("E0,Emin", [(0., 0.), (1., -1.), (1., 2.), (np.nan, 0.)])
def test_invalid_phase_moduli(E0, Emin):
    with pytest.raises(ValueError, match="Emin"):
        law_for().stiffness(np.array([.5]), E0, Emin)
