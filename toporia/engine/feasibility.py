# engine/feasibility.py — did a result honour the scenario's limits?
#
# An optimiser that cannot satisfy every limit at once does not stop with an
# error: it settles on a compromise.  Asked for a stress limit that cannot be
# met within the volume budget, MMA meets the stress limit and quietly uses
# more material than allowed.  Such a result looks like any other unless
# someone reads the constraint values in the history.
#
# So after every run the engine checks each limit explicitly — the volume
# budget, which every method enforces, and every scenario constraint — prints
# a warning for each one that is broken, and records the verdict in run.json.
# Constraints are judged on their exact value when the method reports one
# (the true peak stress, not the p-norm standing in for it).

# How far over a limit a result may end and still count as meeting it.
TOLERANCE = 0.01


def check_limits(scenario, responses):
    """Return one entry per limit: {"name", "value", "limit", "satisfied"}.

    `responses` is a method's final responses dict.  A constraint the method
    did not report is listed with "satisfied": None rather than guessed.
    """
    report = []
    volume = responses.get("volume")
    if volume is not None:
        report.append({
            "name": "volume budget",
            "value": float(volume),
            "limit": scenario.volfrac,
            "satisfied": bool(volume <= scenario.volfrac * (1 + TOLERANCE)),
        })

    for i, spec in enumerate(scenario.constraints):
        key = f"constraint_{i}_{spec.get('type')}"
        g = responses.get(f"{key}_exact", responses.get(key))
        name = f"constraint {i + 1} ({spec.get('type')})"
        if g is None:
            report.append({"name": name, "value": None, "limit": spec.get("limit"), "satisfied": None})
            continue
        # Constraints are normalised as value / limit − 1; show them in the
        # user's units when the spec has a limit.
        limit = spec.get("limit")
        value = (1.0 + g) * limit if limit is not None else g
        report.append({
            "name": name,
            "value": float(value),
            "limit": limit if limit is not None else 0.0,
            "satisfied": bool(g <= TOLERANCE),
        })
    return report


def describe_violations(report):
    """One readable line per broken limit; empty when every limit is met."""
    lines = []
    for entry in report:
        if entry["satisfied"] is False:
            over = entry["value"] / entry["limit"] - 1.0 if entry["limit"] else None
            amount = f" ({over:.1%} over)" if over is not None else ""
            lines.append(f"{entry['name']} not met: {entry['value']:.4g} against a limit of "
                         f"{entry['limit']:.4g}{amount}")
    return lines
