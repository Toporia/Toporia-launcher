# checks/representation.py — is a design representation sound?
#
# The density field it gives has the mesh's shape and stays in [0, 1]; the
# start design lies within the bounds; backward() is the derivative of
# density() (central finite differences, at a perturbed start design); and a
# short run of q4+mma — an updater that works with any representation — stays
# finite.

import numpy as np

from toporia.framework.params import resolve_params
from toporia.framework.problem.mesh import make_problem

from .common import check_declaration, gradient_check, in_dims, iterate, registered, small_run
from .report import Report


def check_representation(cls):
    """Check a Representation: field shape and range, start within bounds, backward, and a short run."""
    from toporia.plugins.representations import REPRESENTATIONS
    report = Report(f"representation {cls.__name__} ({getattr(cls, 'name', '?')})")
    check_declaration(report, cls)
    if not report.ok:
        return report
    run = in_dims(small_run(m=0.4), getattr(cls, "dims", None))
    problem = make_problem(run.scenario, run.solver.m)
    representation = cls(**resolve_params(cls.name, cls.params, {}))

    with report.step("start design within the bounds, field of the mesh's shape in [0, 1]") as check:
        representation.setup(problem)
        z0 = np.asarray(representation.initial(), dtype=float)
        lower, upper = (np.asarray(b, dtype=float) for b in representation.bounds())
        assert lower.shape == z0.shape and upper.shape == z0.shape, \
            f"bounds have shapes {lower.shape}, {upper.shape}; the variables {z0.shape}"
        assert np.all(lower <= z0) and np.all(z0 <= upper), "the start design is outside the bounds"
        field = representation.density(z0)
        assert np.shape(field) == problem.shape, \
            f"density() gave shape {np.shape(field)}, expected {problem.shape}"
        assert np.all(np.isfinite(field)) and field.min() >= -1e-9 and field.max() <= 1 + 1e-9, \
            "density() left [0, 1]"
        check.detail = f"{z0.size} variables, start volume {float(np.mean(field)):.3f}"
    if not report.ok:
        return report

    # Perturbed inside the bounds, so no derivative is checked at a kink of the start layout.
    rng = np.random.default_rng(0)
    movable = upper > lower
    z = np.clip(z0 + np.where(movable, rng.uniform(-0.02, 0.02, z0.shape) * (upper - lower), 0.0), lower, upper)
    weights = rng.normal(size=problem.shape)
    gradient_check(lambda v: float(np.sum(weights * representation.density(v))), representation.backward(z, weights),
                   z, movable, report, "backward vs finite differences")

    with registered(REPRESENTATIONS, cls):
        with report.step("short run with q4+mma"):
            from toporia.engine.loop import initialized_method
            run = in_dims(small_run(method="q4+mma", m=0.4, max_iter=4, tol=0.0, representation={"type": cls.name},
                            method_params={"move": 0.02}), getattr(cls, "dims", None))
            method = initialized_method(run)
            iterate(method, 4)
            assert np.all(np.isfinite(method.get_density())), "the design has non-finite entries"
    return report
