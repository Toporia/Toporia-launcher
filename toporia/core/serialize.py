# core/serialize.py — Scenario and Solver as JSON files.
#
# A scenario file describes a problem completely; a solver file describes how
# to solve it.  Both are plain, human-editable JSON with two reserved keys:
#
#     {"kind": "scenario", "format": 1, "Lx": 60.0, "Ly": 20.0, ...}
#
# Loading is strict: an unknown key is an error rather than being dropped, for
# the same reason unknown parameters are (see core/params.py).  Missing keys
# take the dataclass defaults, so a file only needs what differs from them.
#
# fingerprint() hashes the canonical JSON form, so equal definitions get the
# same short id.  Provenance records use it to say "same problem" or "same
# solver" without comparing whole files.

import dataclasses
import hashlib
import json
import typing
from pathlib import Path

from .scenario import Scenario
from .solver import Solver

FORMAT = 1
KINDS = {"scenario": Scenario, "solver": Solver}
_KIND_OF = {cls: kind for kind, cls in KINDS.items()}


def to_dict(obj):
    """Return a dataclass as plain data (nested dataclasses become dicts)."""
    return dataclasses.asdict(obj)


def from_dict(cls, data):
    """Build a dataclass from plain data, converting nested dataclasses and tuples.

    Raises ValueError for a key the dataclass does not have.
    """
    names = {f.name for f in dataclasses.fields(cls)}
    unknown = sorted(set(data) - names)
    if unknown:
        raise ValueError(f"{cls.__name__} has no field(s) {unknown}. Valid fields: {sorted(names)}")
    hints = typing.get_type_hints(cls)
    return cls(**{name: _convert(hints[name], value) for name, value in data.items()})


def _convert(tp, value):
    if dataclasses.is_dataclass(tp):
        return from_dict(tp, value)
    origin, args = typing.get_origin(tp), typing.get_args(tp)
    if origin is list:
        return [_convert(args[0], v) for v in value] if args else list(value)
    if origin is tuple:
        return tuple(_convert(a, v) for a, v in zip(args, value)) if args else tuple(value)
    if tp is float and isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return value


def dump_json(data):
    """Serialise plain data to indented JSON, accepting NumPy scalars and paths."""
    return json.dumps(data, indent=2, default=_jsonable)


def _jsonable(value):
    if hasattr(value, "item"):          # NumPy scalar
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not JSON serialisable")


def save(obj, path):
    """Write a Scenario or Solver to `path` as JSON and return the path."""
    kind = _KIND_OF.get(type(obj))
    if kind is None:
        raise TypeError(f"Only {sorted(KINDS)} can be saved, not {type(obj).__name__}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json({"kind": kind, "format": FORMAT, **to_dict(obj)}) + "\n", encoding="utf-8")
    return path


def load(path, kind=None):
    """Read a Scenario or Solver from a JSON file.

    `kind` ("scenario" or "solver"), if given, is checked against the file, so
    passing a solver file where a scenario is expected fails with a clear message.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    found = data.pop("kind", None)
    version = data.pop("format", None)
    if found not in KINDS:
        raise ValueError(f"{path}: 'kind' must be one of {sorted(KINDS)}, got {found!r}")
    if kind is not None and found != kind:
        raise ValueError(f"{path} is a {found} file, but a {kind} file was expected")
    if not isinstance(version, int) or version > FORMAT:
        raise ValueError(f"{path}: unsupported format {version!r} (this Toporia reads format {FORMAT})")
    return from_dict(KINDS[found], data)


def fingerprint(obj):
    """Return a short, stable hash of a Scenario or Solver definition."""
    canonical = json.dumps(to_dict(obj), sort_keys=True, separators=(",", ":"), default=_jsonable)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
