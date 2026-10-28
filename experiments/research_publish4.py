"""Publish reviewed Batch 4 evidence; numerical checks never certify papers."""

import argparse
import html
import json
import shutil
from pathlib import Path

from toporia.apps.research_render import description_page
from toporia.plugins.problems._research_batch4 import CASES, POSTS, description, metadata

ROOT = Path(__file__).resolve().parents[1]
CASE_IDS = [k for k in CASES if not k.startswith("post")] + list(POSTS)
NEXT = {
    "solid3d": "Recover a numbered top3d paper panel; align discrete depth loads before any full-field comparison. Keep the 39-step scalar oracle scope separate from the production companion.",
    "heat2d": "Select a numbered FVM heat example and compare its harmonic/arithmetic face conductivity with this Q4 FE interpolation; do not relabel the strip as a source topology.",
    "heat3d": "Choose a genuine 3D source benchmark with complete heat source, sink and material scaling; the depth-uniform strip is an analytic verification only.",
    "elastic_pymoto": "Choose a published benchmark in addition to the fixed-design independent assembly check; align filter/pinning and all load cases.",
    "heat_pymoto": "Align a source heat design; keep cross-implementation value/gradient agreement separate from optimized paper-figure reproduction.",
    "dynamic_pymoto": "Retain common uniform-start normalization for gradient comparisons. Recover a numbered payload-beam source example and match mass interpolation and mode aggregation.",
    "dynamic": "Recover the exact Du-Olhoff payload, end supports and numbered panel. Compare mode subspaces at crossings rather than arbitrary individual eigenvector signs.",
    "frequency_limit": "Align eigenvalue units, the chosen soft minimum and a named feasible source problem; inspect both the aggregate constraint and true first frequency.",
    "harmonic": "Choose a genuinely frequency-domain undamped benchmark or implement a separate damped/transient formulation. PolyDyna's HHT-alpha time response is not the present amplitude equation.",
    "buckling": "Align source pre-stress interpolation and KS aggregation rather than assuming the inverse-factor p-norm is topBuck250. Recover a numbered design beyond the independent Euler column.",
    "nonlinear": "Recover a numbered Buhl/Wang setup, constitutive law, load increments and void blending; compare full equilibrium/adjoint histories and retain Newton failures.",
    "mechanism": "Recover the source inverter's port spring constants, mesh and boundary conditions; compare signed output and thresholded connectivity as well as the reciprocal fixed-field check.",
    "multires": "Align the source's three grids/projection and centroid integration, or identify this Galerkin variant separately. The fine-Q4 stiffness discrepancy is resolved: filters below one analysis cell are refused (coarse/fine 0.986 here).",
    "stress_volume": "Recover a feasible named source stress design; distinguish summed volume objective from the budget and hold adaptive stress scaling fixed during gradient checks.",
    "local_stress": "Match PolyStress mesh, relaxation and AL update rules. Inspect exact relaxed peak and per-element feasibility rather than treating penalty reduction as success.",
    "minimum_length": "Align the original three-field source example, or keep the current nodal-KS physical-field variant separate. Resolve the cone adequately and calibrate curved/diagonal features.",
    "phase_field": "Match a numbered source setup and double-well/normalization/optimizer conventions. A planar Modica-Mortola energy limit is not the source's optimized design.",
}


def publish(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    review_file = destination / "paper-reviews.json"
    reviews = json.loads(review_file.read_text(encoding="utf-8")) if review_file.exists() else {}
    cards, lines = [], ["# Batch 4 cases", "", "Finite execution, independent numerical checks, engineering exports and paper matching are separate.", "",
                        "| Case | Functions | Check | Source comparison | Evidence |", "| :-- | :-- | :-- | :-- | :-- |"]
    for name in CASE_IDS:
        origin, target = source / name, destination / name
        report = json.loads((origin / "report.json").read_text(encoding="utf-8"))
        if not report["checks"]["checks_passed"] or report["iteration_override"] is not None:
            raise ValueError(f"Unreviewed failed/shortened capture: {name}")
        if report["paper_status"] not in {"paper_reproduction_to_fix", "not_applicable_engineering_demo"}:
            raise ValueError("This publisher does not certify paper reproduction")
        preset = report["preset_id"]
        report["limitations"] = CASES[preset]["limits"]
        if name not in POSTS:
            report["source_url"] = CASES[preset]["source"]
            report["target"] = CASES[preset]["target"]
        report["next_check"] = NEXT.get(name, report["next_check"])
        report["primary_source_review"] = reviews.get(name, dict(status="implementation_and_citation_review_only", visual_status="not_assessed"))
        if name in POSTS and report["preset_id"] == "post3d":
            report["original_source_field"] = report["source_field"]
            report["source_field"] = "docs/research/evidence/batch4/solid3d/final-density.npy"
        target.mkdir(parents=True, exist_ok=True)
        (target / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        (target / "description.html").write_text(description_page(metadata(preset)[0], description(preset)), encoding="utf-8")
        for filename in ("figure.png", "initial-density.npy", "final-density.npy", "input-density.npy", "final-variables.npy",
                         "history.csv", "responses.json", "analytic-curve.csv", "frequency-response.csv", "native-scalar-comparison.json"):
            if (origin / filename).is_file():
                shutil.copyfile(origin / filename, target / filename)
        if (origin / "exports").is_dir():
            (target / "exports").mkdir(exist_ok=True)
            for path in (origin / "exports").iterdir():
                if path.suffix in {".svg", ".dxf", ".stl", ".png", ".csv", ".npy"}:
                    shutil.copyfile(path, target / "exports" / path.name)
        queue = ROOT / "docs/research/to-fix" / ("batch4-"+name)
        queue.mkdir(parents=True, exist_ok=True)
        (queue / "README.md").write_text(
            f"# {name}: source comparison and remaining work\n\nFunctions: {', '.join(report['functions'])}\n\n"
            f"Target: {report['target']}\n\nStatus: {report['paper_status']}. Independent checks passed within their reported scope.\n\n"
            f"Limits: {report['limitations']}\n\nNext: {report['next_check']}\n\n"
            f"[Figure](../../evidence/batch4/{name}/figure.png) · [Report](../../evidence/batch4/{name}/report.json) · "
            f"[Math](../../evidence/batch4/{name}/description.html)\n", encoding="utf-8")
        label = CASES[preset]["label"] if name in CASES else name
        exports = " · ".join(f'<a href="{name}/exports/{html.escape(filename, quote=True)}">{html.escape(filename)}</a>'
                             for filename in report.get("files", []))
        lines.append(f"| {label} | {', '.join(report['functions'])} | passed in recorded scope | {report['paper_status']} | "
                     f"[figure](evidence/batch4/{name}/figure.png), [math](evidence/batch4/{name}/description.html), [report](evidence/batch4/{name}/report.json) |")
        cards.append(f'<article><h2>{html.escape(label)}</h2><p><b>{html.escape(report["paper_status"])}</b></p>'
                     f'<a href="{name}/figure.png"><img src="{name}/figure.png" alt="{html.escape(label)}"></a>'
                     f'<p>{html.escape(report["limitations"])}</p><p><a href="{name}/description.html">Description and math</a> · '
                     f'<a href="{name}/report.json">Numerical evidence</a> · '
                     f'<a href="../../to-fix/batch4-{name}/README.md">Remaining work</a></p><p>{exports}</p></article>')
    (destination / "index.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Batch 4 figures</title>'
        '<style>body{font:16px/1.6 system-ui;max-width:1100px;margin:30px auto;padding:0 24px;color:#142338}'
        'article{border-top:1px solid #cad8e1;padding-top:20px;margin-top:30px}img{max-width:100%;height:auto}a{color:#185d8a}</style>'
        '<h1>Batch 4: physics, responses and post-processing</h1><p>25 demonstrations for 39 remaining functions. '
        'No new full paper reproduction is certified. Saved fields are reused for post-processing; engineering exports have no single originating paper.</p>'
        +"\n".join(cards)+"</html>", encoding="utf-8")
    (destination.parents[1] / "batch-4-cases.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(f"Published {len(CASE_IDS)} Batch 4 cases")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/research/batch4/generated")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/research/evidence/batch4")
    args = parser.parse_args()
    publish(args.input, args.output)
