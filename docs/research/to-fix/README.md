# Figure reproduction to fix

This queue stores attempted cases whose required evidence did not match, or
whose paper/setup information is missing. Untouched backlog entries remain in
the coverage inventory; do not pretend they have been attempted.

Batch 2 contributes 17 unresolved paper cases and a separate original-2017
ordered-SIMP target. The volume-preserving-projection companion also has a
documented numerical failure and is quarantined outside preset discovery.
See the [Batch 2 report](../batch-2.md) and [case index](../batch-2-cases.md).

Batch 3 adds 31 unresolved comparisons for 30 functions, including both MMC
thickness variants. Every case has an executed companion, saved fields,
mathematical description and a specific next check. The PTO entry also retains
an author-code comparison on the published MBB setup. See [Batch 3](../batch-3.md)
and its [case index](../batch-3-cases.md). These records do not mean all original
paper figures have been attempted with completely recovered settings.

Batch 4 supplies 25 records covering the remaining 39 functions. Twenty-one
source comparisons remain unresolved; four own connectivity/export examples
have no single originating paper and are marked not applicable. Their queue
entries describe calibration/engineering follow-ups rather than failed paper
matches. See [Batch 4](../batch-4.md), the [case index](../batch-4-cases.md) and
the [framework assessment](../framework-assessment.html).

For each unresolved case create a folder containing:

- `README.md`: function IDs, paper/panel, discrepancy and next useful check.
- Runnable preset or command, with all settings and source identity.
- Numerical report and generated comparison figure, if execution was possible.
- Explicit reason: missing source/settings, incompatible formulation, numerical
  mismatch, nonconvergence or failed feasibility.

The experiment driver also writes numerical failures under its output folder's
`to-fix/` directory and exits nonzero. Promote a compact reviewed record here
when an investigation remains unresolved at the end of a batch.
