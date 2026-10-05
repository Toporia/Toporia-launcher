# toporia/testing.py — the conformance test for a new plugin.
#
# Point it at a class and it checks everything Toporia relies on, then says
# what passed, what failed and why:
#
#     from toporia.testing import conformance
#     conformance(MyUpdater).assert_ok()          # in a test
#     print(conformance(MyUpdater))               # a readable report
#
# or, from the command line:  toporia check updater:my_updater
#
#   every plugin   name, label, parameters that resolve to their defaults
#   Updater        a short run on a problem with holes (finite, inside the
#                  bounds, no thread left behind); a benchmark on the MBB beam,
#                  within `tolerance` of optimality criteria's compliance
#                  and within the volume budget
#   Model          bounds and shapes; volume_of agrees with evaluate; values
#                  without gradients equal values with them; every gradient
#                  against central finite differences
#   Physics        the same, through a model assembled on it
#   Filter         output shape and range; the adjoint against finite
#                  differences (unless the filter declares exact_adjoint = False)
#   Response       its gradient against finite differences, on every engine
#                  that provides the features it requires
#   whole method   a short run (finite, inside the bounds)
#
# The checks only use the public plugin interfaces, so they apply unchanged to
# a plugin that lives in another package.

import contextlib
import io
import threading
import traceback
from dataclasses import dataclass, field

import numpy as np

from toporia.core.composition import ComposedMethod, Model, Updater
from toporia.core.contract import OBJECTIVE, OptimizationMethod
from toporia.core.params import resolve_params
from toporia.core.physics import Physics
from toporia.core.problem import RectangularProblem
from toporia.core.responses import CONSTRAINT_ROLE, OBJECTIVE_ROLE, Response

#: Problems the checks run on: the classic benchmark, and one with holes and solid rings.
BENCHMARK, WITH_HOLES = "MBB Beam", "Drone Arm"


# ── The report ────────────────────────────────────────────────────────────────

@dataclass
class Check:
    name: str
    passed: bool | None      # None: not applicable, skipped
    detail: str = ""


@dataclass
class Report:
    """The outcome of a conformance check: one line per check."""
    subject: str
    checks: list = field(default_factory=list)

    def add(self, name, passed, detail=""):
        self.checks.append(Check(name, passed, detail))

    @property
    def ok(self):
        return all(check.passed is not False for check in self.checks)

    def __str__(self):
        mark = {True: "PASS", False: "FAIL", None: "skip"}
        lines = [f"{self.subject}: {'conforms' if self.ok else 'DOES NOT CONFORM'}"]
        for check in self.checks:
            lines.append(f"  {mark[check.passed]}  {check.name}" + (f" — {check.detail}" if check.detail else ""))
        return "\n".join(lines)

    def assert_ok(self):
        if not self.ok:
            raise AssertionError(str(self))
        return self

    @contextlib.contextmanager
    def step(self, name):
        """Run one check and record it: passed, failed with the exception, or skipped.

        The body may set `.detail` on the yielded Check to say what was measured.
        """
        check = Check(name, True)
        try:
            yield check
        except _Skip as skip:
            check.passed, check.detail = None, str(skip)
        except Exception as error:  # noqa: BLE001 — every failure belongs in the report
            last = traceback.extract_tb(error.__traceback__)[-1]
            where = f"{last.filename.replace(chr(92), '/').rsplit('/', 1)[-1]}:{last.lineno}"
            check.passed, check.detail = False, f"{type(error).__name__}: {error} ({where})"
        self.checks.append(check)


class _Skip(Exception):
    pass


# ── Entry point ───────────────────────────────────────────────────────────────

def conformance(plugin, **options):
    """Check any plugin class (or "kind:name", e.g. "updater:mma") and return a Report.

    The runs inside print nothing: the report is the output.
    """
    with contextlib.redirect_stdout(io.StringIO()):
        return _conformance(plugin, **options)


def parts_of(run):
    """The plugins a run is made of, as "kind:name": its model and updater (or whole
    method), its filters, and its objective and constraint responses."""
    from toporia.library.methods import method_class
    method_cls = method_class(run.solver.method)
    if issubclass(method_cls, ComposedMethod):
        parts = [f"model:{method_cls.model.name}", f"updater:{method_cls.updater.name}"]
    else:
        parts = [f"method:{method_cls.name}"]
    if method_cls.capabilities.accepts_filters:
        parts += [f"filter:{spec.get('type', 'density')}" for spec in run.solver.filter_specs]
    parts.append(f"response:{run.scenario.objective.get('type', 'compliance')}")
    parts += [f"response:{spec['type']}" for spec in run.scenario.constraints]
    return list(dict.fromkeys(parts))


def _conformance(plugin, **options):
    if isinstance(plugin, str):
        plugin = _lookup(plugin)
    checks = ((Updater, check_updater), (Model, check_model), (Physics, check_physics),
              (Response, check_response), (OptimizationMethod, check_method))
    for base, check in checks:
        if isinstance(plugin, type) and issubclass(plugin, base):
            return check(plugin, **options)
    from toporia.library.filters.filter_base import Filter
    if isinstance(plugin, type) and issubclass(plugin, Filter):
        return check_filter(plugin, **options)
    raise TypeError(f"{plugin!r} is not a Toporia plugin class")


def all_plugins():
    """Every registered plugin, as "kind:name" strings."""
    from toporia.library.filters import FILTERS
    from toporia.library.methods import METHODS
    from toporia.library.models import MODELS
    from toporia.library.responses import RESPONSES
    from toporia.library.updaters import UPDATERS
    return [f"{kind}:{name}" for kind, registry in (("model", MODELS), ("updater", UPDATERS),
                                                    ("filter", FILTERS), ("response", RESPONSES),
                                                    ("method", METHODS))
            for name in registry.names()]


def _lookup(text):
    from toporia.library.filters import FILTERS
    from toporia.library.methods import METHODS
    from toporia.library.models import MODELS
    from toporia.library.responses import RESPONSES
    from toporia.library.updaters import UPDATERS
    registries = {"model": MODELS, "updater": UPDATERS, "filter": FILTERS,
                  "response": RESPONSES, "method": METHODS}
    kind, _, name = text.partition(":")
    if kind not in registries or not name:
        raise ValueError(f"Name a plugin as kind:name with kind one of {sorted(registries)}, got {text!r}")
    return registries[kind].get(name)


# ── Shared pieces ─────────────────────────────────────────────────────────────

def _declaration(report, cls):
    with report.step("declaration: name, label and parameters") as check:
        assert getattr(cls, "name", ""), "name is empty, so the plugin cannot be registered"
        assert getattr(cls, "label", ""), "label is empty, so menus would show nothing"
        names = [p.name for p in cls.params]
        assert len(names) == len(set(names)), f"duplicate parameter names in {names}"
        resolve_params(cls.name, cls.params, {})
        check.detail = f"{len(names)} parameter(s)"


@contextlib.contextmanager
def _registered(registry, cls):
    """Make `cls` reachable by name for the duration of a check, if it is not already."""
    known = cls.name in registry and registry.get(cls.name) is cls
    if not known:
        registry.register(cls)
    try:
        yield
    finally:
        if not known:
            registry.unregister(cls.name)


def _run(problem=BENCHMARK, **values):
    from toporia.library.problems import get_run
    values.setdefault("m", 0.4)
    values.setdefault("save_every", 0)
    return get_run(problem).updated(**values)


def _iterate(method, iterations, tol=0.0):
    """Step as the engine does, with its stopping rule (design change below tol, or the method's own)."""
    for iteration in range(1, iterations + 1):
        method.step(iteration)
        if method.get_change() < tol or method.is_converged():
            break


def _gradient_check(value, gradient, x, movable, report, name, count=6, h=1e-5, rtol=1e-3):
    """Compare `gradient` with central differences of `value` at the largest movable entries."""
    with report.step(name) as check:
        gradient = np.asarray(gradient, dtype=float)
        assert gradient.shape == np.shape(x), f"gradient has shape {gradient.shape}, design {np.shape(x)}"
        assert np.all(np.isfinite(gradient)), "gradient has non-finite entries"
        candidates = np.flatnonzero(np.asarray(movable).reshape(-1))
        if candidates.size == 0:
            raise _Skip("no movable variables")
        order = candidates[np.argsort(-np.abs(gradient.reshape(-1)[candidates]))][:count]
        scale = max(float(np.max(np.abs(gradient))), 1e-300)
        worst, where = 0.0, None
        for index in order:
            plus, minus = np.array(x, dtype=float), np.array(x, dtype=float)
            plus.reshape(-1)[index] += h
            minus.reshape(-1)[index] -= h
            fd = (value(plus) - value(minus)) / (2 * h)
            exact = gradient.reshape(-1)[index]
            error = abs(fd - exact) / max(abs(fd), abs(exact), 1e-6 * scale)
            if error > worst:
                worst, where = error, (int(index), exact, fd)
        assert worst <= rtol, (f"off by {worst:.2%} at flat index {where[0]}: "
                               f"gradient {where[1]:.6g}, finite difference {where[2]:.6g}")
        check.detail = f"largest relative error {worst:.1e} over {len(order)} entries"


def _random_design(model, seed=0):
    lower, upper = model.bounds()
    rng = np.random.default_rng(seed)
    x = np.asarray(model.initial_design(), dtype=float) + rng.uniform(-0.15, 0.15, np.shape(lower))
    return np.clip(x, np.maximum(lower, 0.05), np.maximum(np.minimum(upper, 0.95), lower))


def _no_threads_left(report):
    with report.step("no background thread left running"):
        alive = [t.name for t in threading.enumerate() if t.name.startswith("toporia-")]
        assert not alive, f"still running: {alive}"


# ── Updater ───────────────────────────────────────────────────────────────────

_reference = {}


def _oc_compliance(m, max_iter):
    """Optimality criteria's compliance on the benchmark: what an updater is measured against."""
    key = (m, max_iter)
    if key not in _reference:
        from toporia.library.methods import method_class
        run = _run(method="q4+oc", m=m, max_iter=max_iter, tol=0.01)
        method = method_class("q4+oc")()
        method.initialize(RectangularProblem(run.scenario, run.solver.m), run.solver)
        _iterate(method, max_iter, tol=0.01)
        _reference[key] = float(method._model.evaluate(method.x, gradients=False).objective)
    return _reference[key]


def check_updater(cls, model="q4", benchmark=True, tolerance=0.10, m=0.4, max_iter=200):
    """Check an Updater: a short run on a problem with holes, and the MBB benchmark against OC."""
    from toporia.engine.runner import initialized_method
    from toporia.library.methods import method_class
    from toporia.library.updaters import UPDATERS

    report = Report(f"updater {cls.__name__} ({getattr(cls, 'name', '?')})")
    _declaration(report, cls)
    if not report.ok:
        return report
    with _registered(UPDATERS, cls):
        method_cls = method_class(f"{model}+{cls.name}")
        with report.step(f"short run on the {WITH_HOLES} with {model}") as check:
            run = _run(WITH_HOLES, method=method_cls.name, m=0.3, max_iter=4, tol=0.0, volfrac=0.4)
            method = initialized_method(run)
            try:
                _iterate(method, 4)
            finally:
                method.close()
            density = method.get_density()
            lower, upper = method.problem.lower_bound, method.problem.upper_bound
            assert np.all(np.isfinite(density)), "the design has non-finite entries"
            x = method.x
            assert np.all(x >= lower - 1e-9) and np.all(x <= upper + 1e-9), "a design variable left its bounds"
            assert np.isfinite(method.get_responses()[OBJECTIVE]), "the objective is not finite"
            check.detail = f"{method.get_responses().get('solves', '?')} solves in 4 iterations, bounds respected"
        _no_threads_left(report)

        with report.step(f"benchmark: {BENCHMARK}, compliance within {tolerance:.0%} of OC") as check:
            if not benchmark:
                raise _Skip("not requested")
            if "compliance" not in method_cls.capabilities.objectives:
                raise _Skip("cannot minimise compliance")
            run = _run(method=method_cls.name, m=m, max_iter=max_iter, tol=0.01)
            method = initialized_method(run)
            try:
                _iterate(method, max_iter, tol=0.01)
                # One more evaluation, so the objective belongs to the final design.
                final = method._model.evaluate(method.x, gradients=False) \
                    if isinstance(method, ComposedMethod) else None
            finally:
                method.close()
            compliance = final.objective if final is not None else method.get_responses()[OBJECTIVE]
            volume = float(method.get_density().mean())
            reference = _oc_compliance(m, max_iter)
            assert volume <= run.scenario.volfrac * 1.01, f"volume {volume:.3f} exceeds the budget"
            ratio = compliance / reference
            assert ratio <= 1 + tolerance, f"compliance {compliance:.4g} is {ratio - 1:.1%} above OC's {reference:.4g}"
            check.detail = (f"compliance {compliance:.4g} vs OC {reference:.4g} ({ratio - 1:+.1%}), "
                            f"volume {volume:.3f}")
        _no_threads_left(report)
    return report


# ── Model and Physics ─────────────────────────────────────────────────────────

def _model_run(cls, problem=WITH_HOLES):
    """A run that makes the model compute its objective and, if it can, one constraint."""
    from toporia.library.responses import RESPONSES
    capabilities = cls.capabilities
    objective = "compliance" if "compliance" in capabilities.objectives else capabilities.objectives[0]
    constraints = []
    if capabilities.constraints and capabilities.max_constraints != 0:
        response = RESPONSES.get(capabilities.constraints[0])
        constraints = [{"type": response.name, **getattr(response, "gradient_check_settings", {})}]
    return _run(problem, m=0.3, volfrac=0.4, objective={"type": objective}, constraints=constraints)


def check_model(cls):
    """Check a Model: shapes and bounds, consistency, and every gradient by finite differences."""
    report = Report(f"model {cls.__name__} ({getattr(cls, 'name', '?')})")
    _declaration(report, cls)
    if not report.ok:
        return report
    run = _model_run(cls)
    problem = RectangularProblem(run.scenario, run.solver.m)
    model = cls()
    with report.step("initialize on a problem with holes") as check:
        model.initialize(problem, run.solver, resolve_params(cls.name, cls.params, {}))
        check.detail = (f"objective {run.scenario.objective['type']}, constraints "
                        f"{[c['type'] for c in run.scenario.constraints] or 'none'}")
    if not report.ok:
        return report

    with report.step("bounds, start design and physical density"):
        lower, upper = model.bounds()
        x0 = np.asarray(model.initial_design())
        assert np.shape(lower) == np.shape(upper) == x0.shape, "bounds and start design differ in shape"
        assert np.all(lower <= upper), "a lower bound exceeds its upper bound"
        assert np.all(x0 >= lower - 1e-12) and np.all(x0 <= upper + 1e-12), "the start design is out of bounds"
        density = model.physical(x0)
        assert density.shape == (problem.nely, problem.nelx), f"physical() returned shape {density.shape}"
        assert density.min() >= -1e-9 and density.max() <= 1 + 1e-9, "physical density outside [0, 1]"

    x = _random_design(model)
    with report.step("evaluate: values with and without gradients agree"):
        full = model.evaluate(x)
        light = model.evaluate(x, gradients=False)
        assert light.objective == full.objective, "the objective changes when gradients are skipped"
        assert len(light.constraints) == len(full.constraints) == len(run.scenario.constraints), \
            "the number of constraints does not match the scenario"
        assert light.objective_gradient is None, "gradients=False still returned an objective gradient"
        assert np.isclose(model.volume_of(x), full.volume, rtol=1e-10), "volume_of disagrees with evaluate().volume"
    if not report.ok:
        return report

    movable = upper > lower
    _gradient_check(lambda y: model.evaluate(y, gradients=False).objective, full.objective_gradient,
                    x, movable, report, "objective gradient vs finite differences")
    _gradient_check(lambda y: model.evaluate(y, gradients=False).volume, full.volume_gradient,
                    x, movable, report, "volume gradient vs finite differences")
    for i, constraint in enumerate(full.constraints):
        _gradient_check(lambda y, i=i: model.evaluate(y, gradients=False).constraints[i].value,
                        constraint.gradient, x, movable, report,
                        f"constraint {i} ({constraint.name}) gradient vs finite differences")
    return report


def check_physics(cls):
    """Check a Physics engine by checking a model assembled on it."""
    from toporia.library.models.assembled import AssembledModel
    model = type(f"{cls.__name__}Model", (AssembledModel,),
                 {"name": f"checked_{cls.name}", "label": cls.label, "physics": cls})
    report = check_model(model)
    report.subject = f"physics {cls.__name__} ({cls.name}), through an assembled model"
    report.checks.insert(0, Check("provides", True, ", ".join(cls.provides) or "nothing"))
    return report


# ── Filter ────────────────────────────────────────────────────────────────────

def check_filter(cls):
    """Check a Filter: output shape and range, its adjoint, and a short run behind it."""
    from toporia.library.filters import FILTERS
    report = Report(f"filter {cls.__name__} ({getattr(cls, 'name', '?')})")
    _declaration(report, cls)
    if not report.ok:
        return report
    run = _run(m=0.4)
    problem = RectangularProblem(run.scenario, run.solver.m)
    filt = cls(**resolve_params(cls.name, cls.params, {}))
    with report.step("forward: shape and range"):
        filt.setup(problem, run.solver)
        if hasattr(filt, "step"):
            filt.step(10_000)        # end of any continuation: the sharpest, least linear state
        rng = np.random.default_rng(0)
        x = rng.uniform(0.05, 0.95, (problem.nely, problem.nelx))
        y = filt.forward(x)
        assert np.shape(y) == x.shape, f"forward returned shape {np.shape(y)}"
        assert np.all(np.isfinite(y)) and y.min() >= -1e-9 and y.max() <= 1 + 1e-9, "forward left [0, 1]"
    if not report.ok:
        return report

    if getattr(cls, "exact_adjoint", True):
        weights = rng.normal(size=x.shape)
        _gradient_check(lambda z: float(np.sum(weights * filt.forward(z))), filt.backward(x, weights),
                        x, np.ones_like(x, dtype=bool), report, "adjoint (backward) vs finite differences")
    else:
        report.add("adjoint (backward) vs finite differences", None,
                   "declared exact_adjoint = False (a heuristic, not a derivative)")

    with _registered(FILTERS, cls):
        with report.step("short run behind the density filter, with q4+oc"):
            from toporia.engine.runner import initialized_method
            run = _run(method="q4+oc", m=0.4, max_iter=4, tol=0.0,
                       filter_specs=[{"type": "density"}, {"type": cls.name}])
            method = initialized_method(run)
            _iterate(method, 4)
            assert np.all(np.isfinite(method.get_density())), "the design has non-finite entries"
    return report


# ── Response ──────────────────────────────────────────────────────────────────

def check_response(cls):
    """Check a Response: its roles, and its gradient on every engine that can compute it."""
    from toporia.library.models import MODELS
    from toporia.library.models.assembled import AssembledModel
    report = Report(f"response {cls.__name__} ({getattr(cls, 'name', '?')})")
    _declaration(report, cls)
    with report.step("roles") as check:
        assert set(cls.roles) <= {OBJECTIVE_ROLE, CONSTRAINT_ROLE} and cls.roles, f"roles {cls.roles}"
        check.detail = ", ".join(cls.roles)
    if cls.requires is None:
        report.add("gradient vs finite differences", None, "declaration only: computed by a model that names it")
        return report

    engines = [model for model in MODELS.classes()
               if issubclass(model, AssembledModel) and cls.computable_on(model.physics)]
    if not engines:
        report.add("gradient vs finite differences", None, f"no registered engine provides {cls.requires}")
    for model_cls in engines:
        run = _run(WITH_HOLES, m=0.3, volfrac=0.4)
        problem = RectangularProblem(run.scenario, run.solver.m)
        engine = model_cls.physics()
        engine.initialize(problem, resolve_params(model_cls.name, model_cls.params, {}))
        response = cls()
        response.setup(engine, problem, resolve_params(cls.name, cls.params,
                                                       getattr(cls, "gradient_check_settings", {})))
        rng = np.random.default_rng(1)
        density = np.clip(rng.uniform(0.2, 0.9, (problem.nely, problem.nelx)),
                          problem.lower_bound, problem.upper_bound)
        result = response.evaluate(engine.solve(density))
        with report.step(f"on {model_cls.label}: value without the gradient is the same"):
            assert response.evaluate(engine.solve(density), gradient=False).value == result.value
        _gradient_check(lambda d, r=response, e=engine: r.evaluate(e.solve(d), gradient=False).value,
                        result.gradient, density, problem.upper_bound > problem.lower_bound, report,
                        f"on {model_cls.label}: gradient vs finite differences")
    return report


# ── Whole method ──────────────────────────────────────────────────────────────

def check_method(cls):
    """Check a whole method (one that does not split into a model and an updater)."""
    from toporia.library.methods import METHODS
    report = Report(f"method {cls.__name__} ({getattr(cls, 'name', '?')})")
    _declaration(report, cls)
    if issubclass(cls, ComposedMethod):
        report.add("parts", True, f"composed of {cls.model.__name__} and {cls.updater.__name__}")
        report.checks.extend(check_model(cls.model).checks)
        report.checks.extend(check_updater(cls.updater).checks)
        return report
    with _registered(METHODS, cls):
        with report.step("short run on the benchmark"):
            from toporia.engine.runner import initialized_method
            method = initialized_method(_run(method=cls.name, m=0.4, max_iter=5, tol=0.0))
            try:
                _iterate(method, 5)
            finally:
                method.close()
            density = method.get_density()
            assert np.all(np.isfinite(density)) and density.min() >= -1e-9 and density.max() <= 1 + 1e-9
            assert np.isfinite(method.get_responses()[OBJECTIVE])
    return report
