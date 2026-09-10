# core/params.py — self-describing parameters.
#
# Every tunable value in Toporia is declared once, as a Param, next to the code
# that uses it.  From that single declaration:
#
#   - the GUI builds the input widget (range, step, tooltip, units),
#   - sweeps and comparisons know which values exist and can be varied,
#   - a run validates its configuration before any computation starts.
#
# Nothing here imports Qt, NumPy or any algorithm.

from dataclasses import dataclass

KINDS = ("float", "int", "bool", "choice")


@dataclass(frozen=True)
class Param:
    """Declaration of one tunable parameter.

    Attributes
    ----------
    name     : key used in configs, filter specs and parameter paths
    default  : value used when nothing is specified
    label    : short human-readable name for the GUI (defaults to `name`)
    help     : one or two sentences; becomes the tooltip
    kind     : "float" | "int" | "bool" | "choice" — inferred from the default
    min, max : inclusive bounds for numeric kinds (None = unbounded)
    step     : GUI spin-box increment
    decimals : GUI display precision for floats
    choices  : for kind "choice", a tuple of (value, label) pairs
    units    : shown next to the label, e.g. "mm" or "°"
    """

    name: str
    default: object
    label: str = ""
    help: str = ""
    kind: str = ""
    min: float | None = None
    max: float | None = None
    step: float | None = None
    decimals: int | None = None
    choices: tuple = ()
    units: str = ""

    def __post_init__(self):
        kind = self.kind or _infer_kind(self.default, self.choices)
        if kind not in KINDS:
            raise ValueError(f"Param {self.name!r}: kind must be one of {KINDS}, got {kind!r}")
        object.__setattr__(self, "kind", kind)
        if not self.label:
            object.__setattr__(self, "label", self.name)
        # Validate the default against its own declaration, so a typo in a plugin
        # fails when the module is imported rather than halfway through a sweep.
        self.coerce(self.default)

    @property
    def is_numeric(self):
        """True for float and int parameters — the ones a sweep can vary."""
        return self.kind in ("float", "int")

    def coerce(self, value):
        """Return `value` converted to this parameter's type, or raise ValueError.

        Integers are rounded rather than rejected, because sweeps generate
        floats; a choice returns the declared value, so 90.0 becomes 90.
        """
        if self.kind == "bool":
            return bool(value)
        if self.kind == "choice":
            for allowed, _ in self.choices:
                if value == allowed:
                    return allowed
            valid = [allowed for allowed, _ in self.choices]
            raise ValueError(f"{self.name}={value!r} is not one of {valid}")

        value = int(round(value)) if self.kind == "int" else float(value)
        if self.min is not None and value < self.min:
            raise ValueError(f"{self.name}={value} is below its minimum {self.min}")
        if self.max is not None and value > self.max:
            raise ValueError(f"{self.name}={value} is above its maximum {self.max}")
        return value


def _infer_kind(default, choices):
    if choices:
        return "choice"
    if isinstance(default, bool):   # checked first: bool is a subclass of int
        return "bool"
    if isinstance(default, int):
        return "int"
    if isinstance(default, float):
        return "float"
    raise ValueError(f"Cannot infer a Param kind from default {default!r}; pass kind=")


def resolve_params(owner, declared, values=None):
    """Merge `values` over the declared defaults, validating every entry.

    Parameters
    ----------
    owner    : str — who the parameters belong to, for error messages
    declared : iterable of Param
    values   : dict of name -> value, may be partial or None

    An unknown key is an error rather than being ignored.  A misspelt or stale
    parameter would otherwise make a run quietly fall back to a default nobody
    chose — the worst possible failure for a platform whose job is comparison.
    """
    by_name = {p.name: p for p in declared}
    values = dict(values or {})
    unknown = sorted(set(values) - set(by_name))
    if unknown:
        raise ValueError(f"{owner} has no parameter(s) {unknown}. Available: {sorted(by_name)}")
    return {
        name: param.coerce(values[name]) if name in values else param.default
        for name, param in by_name.items()
    }


def select(params, *names):
    """Return the Params with these names, in the order given.

    For building one panel from several declaration groups, e.g. the mesh
    resolution (a Solver field) next to the volume fraction (a Scenario field).
    """
    by_name = {p.name: p for p in params}
    return tuple(by_name[name] for name in names)
