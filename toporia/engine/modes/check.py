# engine/modes/check.py — the "Check Parts" mode: is every part of this run sound?
#
# Instead of optimising, it runs the conformance test (toporia/checks) on each
# plugin the run is made of — its model and updater (or whole method), its
# filters, its objective and constraints — and prints one report per part:
# the interface, every gradient against finite differences, and for an
# updater a benchmark against optimality criteria.

from toporia.checks import conformance, parts_of


def check_parts(config):
    """Check every part of `config`'s pipeline, print the reports; True when all conform."""
    parts = parts_of(config)
    print(f"Checking {len(parts)} parts: {', '.join(parts)}\n")
    results = []
    for part in parts:
        report = conformance(part)
        results.append(report.ok)
        print(report, end="\n\n")
    print(f"{sum(results)} of {len(results)} parts conform")
    return all(results)
