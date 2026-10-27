"""Promote reviewed Batch 2 evidence into portable, versioned documentation.

python -m experiments.research_publish --input results/research/batch2/generated
Does not rerun physics or change status to verified merely because a figure exists.
Only explicitly named files are copied; MATLAB sources and ordinary run folders
are not bundled. The target folder is evidence/, since results/ is git-ignored.
"""

import argparse
import html
import json
import shutil
from pathlib import Path

from toporia.apps.research_render import description_page
from toporia.plugins.problems._research_batch2 import CASES, description, metadata

ROOT = Path(__file__).resolve().parents[1]


def publish(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    reviews_path = destination / "paper-reviews.json"
    reviews = json.loads(reviews_path.read_text(encoding="utf-8")) if reviews_path.exists() else {}
    records = []
    for case_id in CASES:
        origin, target = source / case_id, destination / case_id
        report = json.loads((origin / "report.json").read_text(encoding="utf-8"))
        report["limitations"] = CASES[case_id]["limits"]
        if case_id in reviews:
            report["primary_source_review"] = reviews[case_id]
            report["paper_visual_status"] = reviews[case_id]["visual_status"]
        if not report["checks"]["checks_passed"] and not report.get("quarantined_reason"):
            raise ValueError(f"Numerical check failed: {case_id}; inspect before publishing")
        target.mkdir(parents=True, exist_ok=True)
        (target / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (target / "description.html").write_text(description_page(metadata(case_id)[0], description(case_id)), encoding="utf-8")
        for filename in ("figure.png", "curves.csv", "input.csv",
                         "output.csv", "schedule.csv", "companion.csv", "solver-result.json"):
            if (origin / filename).exists():
                shutil.copyfile(origin / filename, target / filename)
        if report["paper_status"] == "paper_reproduction_to_fix" or report["checks"].get("original_2017_reproduction_to_fix"):
            queue = ROOT / "docs/research/to-fix" / ("batch2-" + case_id)
            queue.mkdir(parents=True, exist_ok=True)
            reason = (f"# {CASES[case_id]['label']}: unresolved research comparison\n\n"
                      f"Target: {report['target']}\n\n"
                      f"Known execution issue: {report.get('quarantined_reason') or 'None observed in the recorded checks.'}\n\n"
                      f"Reason: {report['limitations']}\n\n"
                      f"Numerical checks: {report['checks']['checks_passed']}. "
                      "A passing engineering check is not a paper reproduction.\n\n"
                      f"Next: {report.get('next_check', '')}\n")
            reason += f"\n[Figure and numerical report](../../evidence/batch2/{case_id}/report.json) · "\
                      f"[Generated figure](../../evidence/batch2/{case_id}/figure.png)\n"
            (queue / "README.md").write_text(reason, encoding="utf-8")
        records.append(report)
    cards = []
    for record in records:
        case_id = record["case_id"]
        label = CASES[case_id]["label"]
        status = record["paper_status"]
        qualification = "QUARANTINED: " + record["quarantined_reason"] if record.get("quarantined_reason") else ""
        cards.append(f'<article><h2>{html.escape(label)}</h2><p><strong>{html.escape(status)}</strong></p>'
                     f'<p>{html.escape(qualification)}</p>'
                     f'<a href="{case_id}/figure.png"><img src="{case_id}/figure.png" alt="{html.escape(label)}"></a>'
                     f'<p>{html.escape(record["limitations"])}</p>'
                     f'<p><a href="{case_id}/description.html">Description and math</a> · '
                     f'<a href="{case_id}/report.json">Numerical evidence</a></p></article>')
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Batch 2 research figures</title>'
            '<style>body{font:16px/1.6 system-ui,sans-serif;max-width:1100px;margin:30px auto;padding:0 24px;'
            'color:#142338;background:#fff}article{border-top:1px solid #cad8e1;margin-top:32px;padding-top:20px}'
            'img{max-width:100%;height:auto}a{color:#185d8a}</style><h1>Batch 2 research figures</h1>'
            '<p>Numerical checks and research matching are separate. Unresolved paper targets remain in to-fix. '
            'Transfer curves run through the reproduction command; GUI Run is the documented optimization companion.</p>'
            + "\n".join(cards) + '</html>')
    (destination / "index.html").write_text(page, encoding="utf-8")
    lines = ["# Batch 2 cases", "", "Generated from the reviewed evidence records. A numerical check is not a paper match.",
             "", "| Case | Numerical checks | Research comparison | GUI preset | Evidence |",
             "| :-- | :-- | :-- | :-- | :-- |"]
    for record in records:
        case_id = record["case_id"]
        registered = "quarantined" if record.get("quarantined_reason") else "registered companion"
        lines.append(f"| {CASES[case_id]['label']} | {record['checks']['checks_passed']} | "
                     f"{record['paper_status']} | {registered} | "
                     f"[figure](evidence/batch2/{case_id}/figure.png), [report](evidence/batch2/{case_id}/report.json), "
                     f"[math](evidence/batch2/{case_id}/description.html) |")
    (destination.parents[1] / "batch-2-cases.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Published {len(records)} reviewed case records to {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/research/batch2/generated")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/research/evidence/batch2")
    arguments = parser.parse_args()
    publish(arguments.input, arguments.output)
