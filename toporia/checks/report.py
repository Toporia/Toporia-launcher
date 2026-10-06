# checks/report.py — what a conformance check returns: one line per check.
#
# Report.step() runs one check and records it as passed, failed (with the
# exception and the line it came from) or skipped.

import contextlib
import traceback
from dataclasses import dataclass, field

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
        except Skip as skip:
            check.passed, check.detail = None, str(skip)
        except Exception as error:  # noqa: BLE001 — every failure belongs in the report
            last = traceback.extract_tb(error.__traceback__)[-1]
            where = f"{last.filename.replace(chr(92), '/').rsplit('/', 1)[-1]}:{last.lineno}"
            check.passed, check.detail = False, f"{type(error).__name__}: {error} ({where})"
        self.checks.append(check)


class Skip(Exception):
    pass
