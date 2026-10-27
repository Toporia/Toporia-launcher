"""Build the portable core guide and its computation diagram.

python -m experiments.research_docs
Documentation tooling needs markdown-it-py; the installed application does not.
"""

import base64
import html
import re
from io import BytesIO
from pathlib import Path

from toporia.apps.research_render import equation_image

ROOT = Path(__file__).resolve().parents[1]


def flow_diagram(destination):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    figure = Figure(figsize=(12, 3.1), dpi=160, facecolor="white")
    FigureCanvasAgg(figure)
    axis = figure.add_axes((.015, .04, .97, .92))
    axis.set_xlim(0, 12)
    axis.set_ylim(0, 3)
    axis.axis("off")
    blocks = [(0.1, "Representation", "variables to field"), (2.1, "Filters", "field to material"),
              (4.1, "Physics + law", "solve the state"), (6.1, "Responses", "values + gradients"),
              (8.1, "Updater", "next variables"), (10.1, "Stop / output", "check + report")]
    for x, title, subtitle in blocks:
        axis.add_patch(FancyBboxPatch((x, 1.35), 1.72, .95, boxstyle="round,pad=.04,rounding_size=.08",
                                     edgecolor="#648295", facecolor="#edf4f8", linewidth=1.2))
        axis.text(x + .86, 1.95, title, ha="center", va="center", fontsize=10, weight="bold", color="#17384c")
        axis.text(x + .86, 1.6, subtitle, ha="center", va="center", fontsize=8.5, color="#284e63")
        if x < 10:
            axis.add_patch(FancyArrowPatch((x + 1.78, 1.82), (x + 1.98, 1.82), arrowstyle="-|>",
                                          mutation_scale=12, color="#315f79"))
    axis.add_patch(FancyArrowPatch((8.96, 2.32), (.96, 2.32), connectionstyle="arc3,rad=.035",
                                  arrowstyle="-|>", mutation_scale=12, color="#648295", linestyle="--"))
    axis.text(4.96, 2.5, "repeat with updated variables", ha="center", fontsize=8, color="#426173")
    axis.annotate("Exact gradients return through the adjoints of filters and representation",
                  xy=(1.0, .73), xytext=(6.5, .73), ha="center", va="center", fontsize=9,
                  color="#9b5a20", arrowprops={"arrowstyle": "->", "color": "#9b5a20", "lw": 1.4})
    axis.text(6, 2.75, "One optimization iteration", ha="center", fontsize=14, weight="bold", color="#17384c")
    axis.text(6, .17, "Schedules change parameters around the loop; variants evaluate shared variables in multiple states.",
              ha="center", fontsize=9, color="#426173")
    figure.savefig(destination, dpi=160)


def render_guide(markdown):
    from markdown_it import MarkdownIt
    from PIL import Image

    equations = []

    def replace(match):
        latex = match.group(1).strip()
        encoded, _, _ = equation_image(latex)
        with Image.open(BytesIO(base64.b64decode(encoded))) as picture:
            width, height = picture.size
        scale = min(.4, 800 / width)
        tag = (f'<img class="equation" src="data:image/png;base64,{encoded}" '
               f'width="{round(width * scale)}" height="{round(height * scale)}" '
               f'alt="{html.escape(latex, quote=True)}">')
        marker = f"RESEARCHEQUATIONTOKEN{len(equations)}END"
        equations.append((marker, tag))
        return marker

    text = re.sub(r"\$\$(.*?)\$\$", lambda match: "\n\n" + replace(match) + "\n\n", markdown, flags=re.DOTALL)
    text = re.sub(r"(?<!\$)\$([^$\n]+)\$(?!\$)", replace, text)
    text = re.sub(r"\\\((.*?)\\\)", replace, text)
    rendered = MarkdownIt("commonmark", {"html": False}).enable("table").render(text)
    for marker, tag in equations:
        rendered = rendered.replace(marker, tag)
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>How Toporia computes a design</title>'
            '<style>body{font:16px/1.65 system-ui,sans-serif;max-width:1000px;margin:32px auto;padding:0 24px;'
            'color:#142338;background:white}h1,h2{line-height:1.25;color:#214e78}h2{margin-top:36px}'
            'img{max-width:100%;height:auto}.equation{vertical-align:middle}table{border-collapse:collapse;'
            'width:100%;font-size:14px}td,th{padding:9px;border-bottom:1px solid #d6e1e9;text-align:left}'
            'code{font-size:.9em;background:#edf3f7;padding:2px 4px}a{color:#185d8a}'
            '</style>' + rendered + '</html>')


def main():
    folder = ROOT / "docs/research"
    (folder / "assets").mkdir(parents=True, exist_ok=True)
    flow_diagram(folder / "assets/core-flow.png")
    source = folder / "core.md"
    (folder / "core.html").write_text(render_guide(source.read_text(encoding="utf-8")), encoding="utf-8")
    print(folder / "core.html")


if __name__ == "__main__":
    main()
