"""Publish reviewed Batch 3 diagnostics, without promoting them to paper matches.

python -m experiments.research_publish3
Copies only review artifacts, never raw run folders, downloaded papers or logs.
"""

import argparse
import html
import json
import shutil
from pathlib import Path

from experiments.research_batch3 import NEXT_CHECKS
from toporia.apps.research_render import description_page
from toporia.plugins.problems._research_batch3 import CASES, description, metadata

ROOT = Path(__file__).resolve().parents[1]
FILES = ("figure.png", "initial-density.csv", "final-density.csv", "final-variables.csv", "history.csv",
         "responses.json", "probe-density.csv", "probe-variables.csv", "cap-quadrature.csv",
         "primal-latent.json", "adam-recurrence.csv")


def publish(source, destination, pto_attempt=None):
    destination.mkdir(parents=True, exist_ok=True)
    review_path = destination / "paper-reviews.json"
    reviews = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
    records = []
    for case_id, data in CASES.items():
        origin = source / case_id
        report = json.loads((origin / "report.json").read_text(encoding="utf-8"))
        if not report["checks"]["checks_passed"]:
            raise ValueError(f"Failed checks for {case_id}; review and quarantine before publishing")
        if report["iteration_override"] is not None:
            raise ValueError(f"Diagnostic iteration override for {case_id}; execute the full recipe")
        if report["paper_status"] != "paper_reproduction_to_fix":
            raise ValueError("This publisher cannot certify paper reproduction")
        if not (origin / "figure.png").exists():
            raise ValueError(f"Missing figure for {case_id}")
        report["primary_source_review"] = reviews.get(case_id, dict(
            status="citation_metadata_only", visual_status="not_assessed",
            scope="Declared reference only; numbered source panel and inputs still to recover."))
        report["paper_visual_status"] = report["primary_source_review"]["visual_status"]
        report["limitations"] = data["limits"]
        report["target"] = data["target"]
        report["next_check"] = NEXT_CHECKS[case_id]
        report["fresh_constraints_feasible_1e_4"] = all(
            (c["exact"] if c["exact"] is not None else c["value"]) <= 1e-4 for c in report.get("fresh_constraints", []))
        target = destination / case_id
        target.mkdir(parents=True, exist_ok=True)
        (target / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        (target / "description.html").write_text(description_page(metadata(case_id)[0], description(case_id)), encoding="utf-8")
        for filename in FILES:
            if (origin / filename).is_file():
                shutil.copyfile(origin / filename, target / filename)
        queue = ROOT / "docs/research/to-fix" / ("batch3-" + case_id)
        queue.mkdir(parents=True, exist_ok=True)
        text = (f"# {data['label']}: unresolved paper comparison\n\nTarget: {data['target']}\n\n"
                f"Difference/gap: {data['limits']}\n\n"
                f"Recorded execution: {report['iterations']} steps; {report['stop_reason']}. "
                f"Fresh final compliance {report['fresh_final_compliance']:.8g}; physical fraction {report['physical_volume_fraction']:.8g}; "
                f"budget 0.5; within budget +1e-4: {report['feasible_volume_1e_4']}. "
                f"Extra constraints within +1e-4: {report['fresh_constraints_feasible_1e_4']}. "
                "Finite/bounded execution does not establish feasibility, convergence or paper agreement.\n\n"
                f"Next: {report['next_check']}\n\n"
                f"[Figure](../../evidence/batch3/{case_id}/figure.png) · "
                f"[Numerical report](../../evidence/batch3/{case_id}/report.json) · "
                f"[Description and math](../../evidence/batch3/{case_id}/description.html)\n")
        (queue / "README.md").write_text(text, encoding="utf-8")
        records.append(report)
    lines = ["# Batch 3 cases", "", "All 31 cases have unresolved paper comparisons. Numerical checks and finite execution are separate from feasibility and convergence.", "",
             "OC and element densities reuse the verified [Batch 1](batch-1.md) example; they are not recomputed or counted here.", "",
             "| Function / variant | Steps | Fresh C | Fraction | Stop | Evidence |",
             "| :-- | --: | --: | --: | :-- | :-- |"]
    cards = []
    for record in records:
        case_id = record["case_id"]
        label = CASES[case_id]["label"]
        native_link = ('<p><a href="pto/paper-attempt/figure.png">Native PTOc Figure 3 comparison</a> · '
                       '<a href="pto/paper-attempt/report.json">Mismatch report</a></p>'
                       if case_id == "pto" and (pto_attempt is not None or (destination / "pto/paper-attempt/report.json").exists()) else "")
        lines.append(f"| {label} | {record['iterations']} | {record['fresh_final_compliance']:.5g} | "
                     f"{record['physical_volume_fraction']:.6f} | {record['stop_reason']} | "
                     f"[figure](evidence/batch3/{case_id}/figure.png), [math](evidence/batch3/{case_id}/description.html), "
                     f"[report](evidence/batch3/{case_id}/report.json) |")
        cards.append(f'<article><h2>{html.escape(label)}</h2><p><strong>Paper comparison: to fix</strong> · '
                     f'Execution checks: passed · Budget +1e-4: {record["feasible_volume_1e_4"]} · '
                     f'Extra constraints +1e-4: {record["fresh_constraints_feasible_1e_4"]}</p>'
                     f'<a href="{case_id}/figure.png"><img src="{case_id}/figure.png" alt="{html.escape(label)}"></a>'
                     f'<p>{html.escape(record["target"])}</p><p>{html.escape(record["limitations"])}</p>'
                     f'<p>{html.escape(record["stop_reason"])}; fresh compliance {record["fresh_final_compliance"]:.6g}; '
                     f'fraction {record["physical_volume_fraction"]:.6f}; grayness {record["grayness"]:.4f}.</p>'
                     f'<p><a href="{case_id}/description.html">Description and math</a> · '
                     f'<a href="{case_id}/report.json">Numerical evidence</a> · '
                     f'<a href="../../to-fix/batch3-{case_id}/README.md">Next check</a></p>{native_link}</article>')
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Batch 3 research figures</title>'
            '<style>body{font:16px/1.6 system-ui,sans-serif;max-width:1100px;margin:30px auto;padding:0 24px;'
            'color:#142338;background:#fff}article{border-top:1px solid #cad8e1;margin-top:32px;padding-top:20px}'
            'img{max-width:100%;height:auto}a{color:#185d8a}</style><h1>Batch 3: existing optimizers and representations</h1>'
            '<p>31 bounded diagnostics, 30 functions. All paper reproductions remain unresolved. '
            'A passing numerical check is separate from feasibility, convergence and published-figure matching. '
            'The coarser null-space/trust-constr and independent level-set/geometry runs are not a fair optimizer ranking.</p>'
            + "\n".join(cards) + '</html>')
    (destination / "index.html").write_text(page, encoding="utf-8")
    (destination.parents[1] / "batch-3-cases.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    if pto_attempt is not None:
        attempt = json.loads((pto_attempt / "report.json").read_text(encoding="utf-8"))
        if not attempt["author_field_physics_match"] or attempt["native_code_match"]:
            raise ValueError("Unexpected PTO comparison verdict: inspect before promotion")
        target = destination / "pto/paper-attempt"
        target.mkdir(parents=True, exist_ok=True)
        for filename in ("report.json", "figure.png", "toporia-density.csv", "author-density-bottom-origin.csv", "toporia-history.csv"):
            shutil.copyfile(pto_attempt / filename, target / filename)
    reviewed_attempt = destination / "pto/paper-attempt/report.json"
    if reviewed_attempt.exists():
        attempt = json.loads(reviewed_attempt.read_text(encoding="utf-8"))
        note = ROOT / "docs/research/to-fix/batch3-pto/README.md"
        note.write_text(note.read_text(encoding="utf-8") +
                        "\n## Native Figure 3 attempt\n\n"
                        f"Author PTOc stopped at {attempt['author_iterations']} iterations; the Toporia variant reached "
                        f"{attempt['toporia_iterations']}. Relative fresh-compliance difference: "
                        f"{attempt['relative_compliance_error']:.4%}; max density difference: {attempt['density_max_error']:.6f}. "
                        "Both use the paper's distributed three-node loads/supports and fraction 0.35. "
                        "The common physics check on the author field matches its printed compliance within rounding.\n\n"
                        "[Native comparison figure](../../evidence/batch3/pto/paper-attempt/figure.png) · "
                        "[Comparison report](../../evidence/batch3/pto/paper-attempt/report.json)\n", encoding="utf-8")
    print(f"Published {len(records)} Batch 3 diagnostics")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/research/batch3/generated")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/research/evidence/batch3")
    parser.add_argument("--pto-attempt", type=Path, help="Explicitly promote an inspected native PTOc comparison")
    args = parser.parse_args()
    publish(args.input, args.output, args.pto_attempt)
