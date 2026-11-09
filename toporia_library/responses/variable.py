# toporia_library/responses/variable.py — any variable of the problem as an objective or a constraint.
#
# The scenario's variables (toporia_core/framework/variables.py) and every built-in quantity of the
# physics are named; this response minimises one, or limits it:
#
#     objective   = {"type": "variable", "variable": "ratio"}
#     constraints = [{"type": "variable", "variable": "s", "limit": 4.0, "bound": "at_most"}]
#
# As a constraint the value is normalised like every other limit:
#     at most   g = value / limit − 1 ≤ 0
#     at least  g = 1 − value / limit ≤ 0
# The gradient is exact for a measured variable; for a derived one it is the chain rule
# through the formula (toporia_core/framework/variables.py).

from toporia_core.framework.params import Param
from toporia_core.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE, Response, ResponseValue
from toporia_core.framework.variables import NAME, VariableSet


class VariableResponse(Response):
    """One named variable of the problem, minimised or limited."""
    name = "variable"
    label = "A variable of the problem"
    use_when = (
        "To optimise or limit a quantity you defined yourself on the Problem page (a formula of other "
        "variables, or a measured quantity with its own parameters)."
    )
    reference = "Toporia's variable space (toporia_core/framework/variables.py)."
    order = 95
    roles = (OBJECTIVE_ROLE, CONSTRAINT_ROLE)
    requires = ()        # the variable is checked against the physics when the run starts
    structured = ("variable",)
    params = (
        Param("limit", 1.0, "Limit", "As a constraint: the bound on the variable, in its own units.",
              min=-1e12, max=1e12, step=1.0, decimals=6),
        Param("bound", "at_most", "Bound", "As a constraint: whether the variable stays below or above the limit.",
              choices=(("at_most", "at most"), ("at_least", "at least"))),
    )

    @classmethod
    def validate_spec(cls, values):
        """The variable must be named; whether it exists is checked against the run's scenario."""
        if not NAME.fullmatch(str(values.get("variable", ""))):
            raise ValueError(f"A variable response needs the name of a variable, got {values.get('variable')!r}")
        if values.get("limit") == 0:
            raise ValueError("A variable's limit cannot be 0: the constraint is normalised by it")

    @classmethod
    def gradient_check_settings_for(cls, physics):
        """A built-in quantity every physics has: the volume."""
        return {"variable": "volume"}

    def setup(self, physics, problem, settings):
        super().setup(physics, problem, settings)
        specs = getattr(problem.scenario, "variables", None) or []
        self.target = settings["variable"]
        self.variables = VariableSet(physics, problem, specs, wanted=[self.target])

    def evaluate(self, state, gradient=True):
        value, slope = self.variables.evaluate(state, gradient=gradient)[self.target]
        reported = {f"var:{self.target}": value}
        if self.role_is_constraint():
            limit = self.settings["limit"]
            sign = 1.0 if self.settings["bound"] == "at_most" else -1.0
            g = sign * (value / limit - 1.0)
            return ResponseValue(g, None if slope is None else sign * slope / limit, reported=reported)
        return ResponseValue(value, slope, reported=reported)

    def role_is_constraint(self):
        """True when this response was set up as a constraint (the model says so through `role`)."""
        return getattr(self, "role", OBJECTIVE_ROLE) == CONSTRAINT_ROLE
