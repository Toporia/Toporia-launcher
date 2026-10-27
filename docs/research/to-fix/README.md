# Figure reproduction to fix

This queue stores attempted cases whose required evidence did not match, or
whose paper/setup information is missing. Untouched backlog entries remain in
the coverage inventory; do not pretend they have been attempted.

For each unresolved case create a folder containing:

- `README.md`: function IDs, paper/panel, discrepancy and next useful check.
- Runnable preset or command, with all settings and source identity.
- Numerical report and generated comparison figure, if execution was possible.
- Explicit reason: missing source/settings, incompatible formulation, numerical
  mismatch, nonconvergence or failed feasibility.

The experiment driver also writes numerical failures under its output folder's
`to-fix/` directory and exits nonzero. Promote a compact reviewed record here
when an investigation remains unresolved at the end of a batch.
