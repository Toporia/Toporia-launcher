# framework/variables.py — the problem as a space of variables (To do items 1 + 2).
#
# Every quantity a physics can compute is a variable: compliance, volume, peak stress,
# thermal compliance, ...  A scenario can add its own:
#
#     variables = [{"name": "c",     "type": "compliance"},              measured
#                  {"name": "s",     "type": "peak_stress", "p": 8},      measured, with parameters
#                  {"name": "ratio", "expression": "c * s / volume"}]     derived from others
#
# A derived variable may use measured ones, other derived ones, and the built-in names
# of every quantity the physics computes (with default parameters).  Each variable has a
# value and, when asked, an exact gradient with respect to the physical density: measured
# ones from their response, derived ones by the chain rule, with the formula's slope per
# input taken as a central difference of the scalar formula.
#
# Variables are recorded every iteration (as "var:<name>") and become an objective, a
# term of a combined objective, or a constraint through the "variable" response.
#
#   compile_expression   check a formula and make it callable
#   variable_space       every name available on a physics, built in or your own
#   VariableSet          evaluates a scenario's variables on a solved state

import ast
import math
import re

import numpy as np

from toporia_core.framework.companions import set_up_response

FUNCTIONS = {"sqrt": math.sqrt, "exp": math.exp, "log": math.log, "abs": abs, "min": min, "max": max,
             "sin": math.sin, "cos": math.cos, "tanh": math.tanh}
_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.Constant, ast.Call,
          ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd)
NAME = re.compile(r"[A-Za-z_]\w*")


def expression_names(text):
    """The variable names a formula uses (function names left out)."""
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError:
        return set()
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id not in FUNCTIONS}


def compile_expression(text, names, what="The objective expression"):
    """Check a formula over `names` and return a function of a {name: value} dict."""
    try:
        tree = ast.parse(str(text).strip(), mode="eval")
    except SyntaxError as error:
        raise ValueError(f"{what} {text!r} is not valid Python: {error.msg}") from None
    for node in ast.walk(tree):
        if not isinstance(node, _NODES):
            raise ValueError(f"{what} may not use {type(node).__name__}: {text!r}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError(f"{what} may only hold numbers: {text!r}")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS):
            raise ValueError(f"{what} may call only {', '.join(FUNCTIONS)}: {text!r}")
        if isinstance(node, ast.Name) and node.id not in names and node.id not in FUNCTIONS:
            known = ", ".join(sorted(names)) or "none"
            raise ValueError(f"{what} uses {node.id!r}, which is not a variable here; the names are {known}")
    code = compile(tree, "<expression>", "eval")
    return lambda values: float(eval(code, {"__builtins__": {}}, {**FUNCTIONS, **values}))


def formula_slopes(formula, point):
    """The formula's value and its slope with respect to each input, by central differences."""
    value = formula(point)
    slopes = {}
    for name, v in point.items():
        step = 1e-6 * abs(v) if v != 0 else 1e-8
        up, down = dict(point), dict(point)
        up[name], down[name] = v + step, v - step
        slopes[name] = (formula(up) - formula(down)) / (2 * step)
    return value, slopes


def builtin_quantities(physics):
    """The objective-capable responses that compute themselves on `physics`, by name."""
    from toporia_core.framework.parts.response import OBJECTIVE_ROLE
    from toporia_core.framework.registries import responses_for
    return {cls.name: cls for cls in responses_for(OBJECTIVE_ROLE)
            if cls.requires is not None and not cls.structured and cls.computable_on(physics)}


def variable_space(physics, specs=()):
    """Every variable on `physics`: (name, label, kind) with kind "built in", "measured" or "derived"."""
    rows = [(name, cls.label, "built in") for name, cls in builtin_quantities(physics).items()]
    for spec in specs:
        rows.append((spec["name"], spec.get("expression") or spec.get("type", ""),
                     "derived" if "expression" in spec else "measured"))
    return rows


def check_variables(specs, physics=None):
    """Validate a scenario's variables: names, types, formulas, and no cycles.  Returns them ordered."""
    from toporia_core.framework.parts.response import OBJECTIVE_ROLE
    from toporia_core.framework.registries import resolve_response
    builtins = set(builtin_quantities(physics)) if physics is not None else None
    by_name = {}
    for spec in specs:
        if not isinstance(spec, dict) or not NAME.fullmatch(str(spec.get("name", ""))):
            raise ValueError(f"Every variable needs a Python name, got {spec!r}")
        if spec["name"] in by_name or spec["name"] in FUNCTIONS:
            raise ValueError(f"The variable name {spec['name']!r} is used twice or is a function name")
        if ("expression" in spec) == ("type" in spec):
            raise ValueError(f"Variable {spec['name']!r} needs either a 'type' (measured) or an 'expression'")
        if "type" in spec:
            from toporia_core.framework.registries import RESPONSES
            if RESPONSES.get(spec["type"]).structured:
                raise ValueError(f"Variable {spec['name']!r} cannot measure a "
                                 f"{RESPONSES.get(spec['type']).label!r}: use a formula of variables instead")
            resolve_response(_measured_spec(spec), OBJECTIVE_ROLE)
        by_name[spec["name"]] = spec

    order, state = [], {}

    def visit(name, chain):
        if state.get(name) == "done":
            return
        if state.get(name) == "busy":
            raise ValueError(f"The variables depend on each other in a circle: {' -> '.join(chain + [name])}")
        state[name] = "busy"
        spec = by_name[name]
        if "expression" in spec:
            for used in expression_names(spec["expression"]):
                if used in by_name:
                    visit(used, chain + [name])
                elif builtins is not None and used not in builtins:
                    raise ValueError(f"Variable {name!r} uses {used!r}, which is not a variable here")
            compile_expression(spec["expression"], set(by_name) | (builtins or expression_names(spec["expression"])),
                               what=f"The formula of {name!r}")
        state[name] = "done"
        order.append(spec)

    for name in by_name:
        visit(name, [])
    return order


def _measured_spec(spec):
    return {key: value for key, value in spec.items() if key not in ("name", "physics")}


class VariableSet:
    """A scenario's variables, and the built-in quantities they use, evaluated on one physics."""

    def __init__(self, physics, problem, specs, wanted=None):
        """`wanted`: the names needed (with what they use); None means every variable in `specs`."""
        from toporia_core.framework.parts.response import OBJECTIVE_ROLE
        from toporia_core.framework.registries import resolve_response
        self.order = check_variables(specs, type(physics))
        builtins = builtin_quantities(type(physics))
        by_name = {spec["name"]: spec for spec in self.order}
        needed = set()

        def need(name):
            if name in needed:
                return
            needed.add(name)
            for used in expression_names(by_name.get(name, {}).get("expression", "")):
                need(used)

        for name in (list(by_name) if wanted is None else wanted):
            if name not in by_name and name not in builtins:
                raise ValueError(f"There is no variable {name!r} here")
            need(name)
        self.measured, self.derived = {}, []
        for name in sorted(needed):
            if name in by_name and "type" in by_name[name]:
                cls, values = resolve_response(_measured_spec(by_name[name]), OBJECTIVE_ROLE)
            elif name not in by_name and name in builtins:
                cls, values = builtins[name], None
            else:
                continue
            on = by_name.get(name, {}).get("physics")
            if on is None and not cls.computable_on(type(physics)):
                raise ValueError(f"Variable {name!r} ({cls.label}) cannot be computed on {physics.label!r}")
            if values is None:
                _, values = resolve_response({"type": cls.name}, OBJECTIVE_ROLE)
            self.measured[name] = set_up_response(cls, values, physics, problem, on)
        for spec in self.order:
            if spec["name"] in needed and "expression" in spec:
                names = set(self.measured) | {s["name"] for s in self.derived}
                self.derived.append({**spec, "formula": compile_expression(
                    spec["expression"], names, what=f"The formula of {spec['name']!r}")})
        self.names = [spec["name"] for spec in self.order if spec["name"] in needed]

    def evaluate(self, state, gradient=False):
        """{name: (value, gradient or None)} for every variable needed, built-in inputs included."""
        out = {}
        for name, response in self.measured.items():
            result = response.evaluate(state, gradient=gradient)
            out[name] = (float(result.value), None if result.gradient is None else np.asarray(result.gradient))
        for spec in self.derived:
            used = expression_names(spec["expression"])
            point = {name: out[name][0] for name in used}
            if gradient:
                value, slopes = formula_slopes(spec["formula"], point)
                total = sum(slopes[name] * out[name][1] for name in used) if used else 0.0
                out[spec["name"]] = (value, np.asarray(total + np.zeros_like(state.density, dtype=float)))
            else:
                out[spec["name"]] = (spec["formula"](point), None)
        return out
