"""checks — the conformance test a new plugin must pass (see conformance.py)."""

from .conformance import Check, Report, all_plugins, conformance, parts_of

__all__ = ["Check", "Report", "all_plugins", "conformance", "parts_of"]
