"""Generate a traceable function/paper/figure census from actual declarations.

python -m experiments.research_inventory
Only built-in functions are included, so optional externally installed plugins do
not silently change the research backlog. Metadata citations are not treated as
verified paper access, nor are ordinary passing tests called figure reproduction.
"""

import argparse
import ast
import csv
import importlib
import inspect
import json
import pkgutil
import re
from collections import Counter
from pathlib import Path

from toporia.engine.pipeline import registries
from toporia.framework.parts.physics import Physics
from toporia.plugins import physics
from toporia.plugins.problems import _modules, problem_description

ROOT = Path(__file__).resolve().parents[1]
BASELINE = {"model:q4", "physics:q4_plane_stress", "representation:element_density",
            "filter:density", "filter:sensitivity", "interpolation:simp", "response:compliance",
            "updater:oc"}
TARGET_TYPES = {
    "model": "physical benchmark / field / objective",
    "physics": "state or eigenvalue benchmark",
    "updater": "convergence curve and feasible final design",
    "representation": "represented geometry and optimized design",
    "filter": "input/output density field and relevant manufacturing metric",
    "interpolation": "material-property curve and a design example",
    "response": "response curve / field and independent evaluation",
    "schedule": "parameter history and effect on a reference design",
    "method": "convergence curve and final design",
    "postprocessor": "before/after geometry or independently checked metric/export",
}


def _batch(kind):
    if kind in {"filter", "interpolation", "schedule"}:
        return 2
    if kind in {"updater", "representation", "method"}:
        return 3
    return 4


def _row(kind, name, cls):
    reference = getattr(cls, "reference", "")
    source = Path(inspect.getfile(cls)).resolve().relative_to(ROOT).as_posix()
    identity = f"{kind}:{name}"
    baseline = identity in BASELINE
    return {"id": identity, "kind": kind, "label": getattr(cls, "label", name), "source_file": source,
            "reference_declaration": reference,
            "source_urls": re.findall(r"https?://[^\s]+", reference),
            "citation_review": "metadata only; primary-source figure selection pending" if not baseline else
                               "Andreassen Figure 3(a) checked; other citations remain unreviewed in this batch",
            "target_figure": "Andreassen 2011, Figure 3(a), top/bottom" if baseline else "not selected",
            "target_type": TARGET_TYPES[kind], "batch": 1 if baseline else _batch(kind),
            "status": "baseline_example" if baseline else "pending",
            "evidence": ["evidence/top88-density.json", "evidence/top88-sensitivity.json"] if baseline else [],
            "notes": "The baseline volume budget does not exercise this separate minimum-volume objective; its paper example is pending." if identity == "response:volume" else ""}


def inventory():
    functions, errors = [], []
    for kind, registry in registries().items():
        for cls in registry.classes():
            if cls.__module__.startswith("toporia.plugins."):
                functions.append(_row(kind, cls.name, cls))
        errors.extend(str(error) for error in registry.errors)
    for info in pkgutil.iter_modules(physics.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{physics.__name__}.{info.name}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ == module.__name__ and issubclass(cls, Physics) and getattr(cls, "name", ""):
                functions.append(_row("physics", cls.name, cls))
    presets = []
    for name, module in sorted(_modules().items()):
        description = problem_description(name)
        presets.append({"name": name, "source_file": Path(module.__file__).relative_to(ROOT).as_posix(),
                        "about": getattr(module, "ABOUT", ""), "reference": getattr(module, "REFERENCE", ""),
                        "research_description": description is not None,
                        "target_figure": description.figure if description else "not assigned",
                        "functions": list(description.functions) if description else []})
    # Reviewed evidence records, rather than the presence of a picture, supply
    # Batch 2-4 status. Several functions are variants with unresolved paper targets.
    for evidence in sorted((ROOT / "docs/research/evidence").glob("batch[234]/*/report.json")):
        record = json.loads(evidence.read_text(encoding="utf-8"))
        for row in functions:
            if row["id"] in record["functions"]:
                if row.get("research_cases") is None:
                    row["research_cases"] = []
                row["research_cases"].append({
                    "case_id": record["case_id"], "paper_status": record["paper_status"],
                    "target": record["target"], "source_url": record["source_url"],
                    "checks_passed": record["checks"]["checks_passed"],
                    "evidence": evidence.relative_to(ROOT / "docs/research").as_posix()})
                row["batch"] = int(evidence.parent.parent.name.removeprefix("batch"))
                row["target_figure"] = ", ".join(
                    item["case_id"] for item in row["research_cases"])
                matched = any(item["paper_status"] in {"native_code_match", "source_equation_curve_match"}
                              for item in row["research_cases"])
                engineering = all(item["paper_status"] == "not_applicable_engineering_demo" for item in row["research_cases"])
                row["status"] = "research_example_verified" if matched else "engineering_example" if engineering else "paper_reproduction_to_fix"
                row["citation_review"] = "See per-case primary sources and explicit comparison scope; other citations remain unreviewed."
                row["evidence"] = [item["evidence"] for item in row["research_cases"]]
    defined_in = {}
    for row in functions:
        defined_in.setdefault(row["source_file"], []).append(row["id"])
    preset_files = {preset["source_file"] for preset in presets}
    modules = []
    for path in sorted((ROOT / "toporia").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        content = path.read_text(encoding="utf-8-sig")
        docstring = ast.get_docstring(ast.parse(content))
        comments = [line.lstrip("# ") for line in content.splitlines()[:8] if line.startswith("#")]
        summary = (docstring or " ".join(comments) or "Package/support module; see source.").split("\n\n")[0]
        modules.append({"source_file": relative, "defines_functions": defined_in.get(relative, []),
                        "is_preset": relative in preset_files,
                        "classification": "numerical function implementation" if relative in defined_in else
                                          "preset recipe" if relative in preset_files else "supporting module",
                        "source_summary": summary[:500]})
    return {"schema": 1, "scope": "Built-in selectable functions, concrete physics engines and presets; "
            "generated model+updater pairings are not counted again.",
            "functions": sorted(functions, key=lambda row: row["id"]), "presets": presets,
            "modules": modules, "discovery_errors": errors}


def write_inventory(destination):
    destination.mkdir(parents=True, exist_ok=True)
    report = inventory()
    (destination / "inventory.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    fields = ["id", "label", "source_file", "batch", "status", "target_figure", "target_type", "source_urls", "notes"]
    with (destination / "inventory.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({**row, "source_urls": " | ".join(row["source_urls"])} for row in report["functions"])
    counts = Counter(row["kind"] for row in report["functions"])
    lines = ["# Function coverage", "", "Generated by `python -m experiments.research_inventory`. "
             "Baseline examples and Batch 2-4 records distinguish native-code, source-equation and paper-visual evidence. "
             "Unresolved comparisons are marked to fix; untouched targets remain pending. "
             "Metadata citations outside reviewed cases still need primary-source review.",
             "", f"**{len(report['functions'])} functions/engines; {len(report['presets'])} presets.** "
             "Presets are recipes, not extra numerical implementations.", "",
             "| Kind | Count |", "| :-- | --: |"]
    lines += [f"| {kind} | {count} |" for kind, count in sorted(counts.items())]
    lines += ["", "| Function | Batch | Target / status | Implementation |", "| :-- | --: | :-- | :-- |"]
    for row in report["functions"]:
        lines.append(f"| `{row['id']}` | {row['batch']} | {row['target_figure']} / {row['status']} | "
                     f"[code](../../{row['source_file']}) |")
    lines += ["", "[Machine-readable inventory](inventory.json) includes every citation, source file, "
              "preset description and evidence link. [CSV](inventory.csv) supports sorting/filtering."]
    (destination / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    module_lines = ["# Module ownership", "", "Generated from every Python module under `toporia/`. "
                    "A supporting module defines no directly inventoried selectable function/physics engine; "
                    "it may still implement shared mathematics or participate in several functions. "
                    "This is a file ownership map, not a runtime call graph. Source-derived summaries are in inventory.json.",
                    "", "| Module | Classification | Public numerical function IDs |", "| :-- | :-- | :-- |"]
    for row in report["modules"]:
        module_lines.append(f"| [{row['source_file']}](../../{row['source_file']}) | {row['classification']} | "
                            f"{', '.join(row['defines_functions']) or '-'} |")
    (destination / "modules.md").write_text("\n".join(module_lines) + "\n", encoding="utf-8")
    print(json.dumps({"functions": len(report["functions"]), "by_kind": dict(counts),
                      "presets": len(report["presets"]), "discovery_errors": report["discovery_errors"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/research")
    write_inventory(parser.parse_args().output)
