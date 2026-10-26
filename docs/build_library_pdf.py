"""Build the linked library PDF from the catalogue and a dated integration summary.

Run on Windows with Python, ReportLab and Segoe UI fonts. The output replaces
only Toporia-library-with-links.pdf in this checkout; the original scope PDF is
left intact. Source links point at integration/physics, which may be unpublished.
"""

import argparse
import html
import posixpath
import re
from pathlib import Path
from urllib.parse import quote

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Toporia-library-with-links.pdf"
REPOSITORY = "https://github.com/Toporia/Toporia-launcher"
BRANCH = "integration/physics"
STAMP = "26 October 2026"
INK = colors.HexColor("#172947")
BLUE = colors.HexColor("#235bc2")
PALE = colors.HexColor("#eef3fa")
RULE = colors.HexColor("#d7e1ee")
WIDTH = A4[0] - 84


def configure_fonts():
    fonts = Path("C:/Windows/Fonts")
    for name, filename in (("Library", "segoeui.ttf"), ("Library-Bold", "segoeuib.ttf"),
                           ("Library-Italic", "segoeuii.ttf"), ("Library-Code", "consola.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily("Library", normal="Library", bold="Library-Bold", italic="Library-Italic")


def source_url(path):
    target, _, anchor = path.partition("#")
    resolved = posixpath.normpath(posixpath.join("toporia/plugins", target))
    if not (ROOT / resolved).exists():
        raise ValueError(f"Missing linked source: {resolved}")
    result = f"{REPOSITORY}/blob/{BRANCH}/{quote(resolved, safe='/')}"
    return result + (f"#{anchor}" if anchor else "")


def inline(text):
    """Convert the catalogue's small inline Markdown subset to PDF markup."""
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2011", "-")
    tokens = []

    def protect(markup):
        tokens.append(markup)
        return f"@@TOKEN{len(tokens)-1}@@"

    def link(match):
        label, target = match.groups()
        url = target if target.startswith(("https://", "http://", "#")) else source_url(target)
        return protect(f'<link href="{html.escape(url, quote=True)}" color="#235bc2">{html.escape(label)}</link>')

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = re.sub(r"`([^`]+)`", lambda m: protect(f'<font name="Library-Code" size="7.2">{html.escape(m[1])}</font>'), text)
    text = html.escape(text)
    text = text.replace("&lt;br/&gt;", "<br/>")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    for index, markup in enumerate(tokens):
        text = text.replace(f"@@TOKEN{index}@@", markup)
    return text


class LibraryDocument(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        bookmark = getattr(flowable, "bookmark", None)
        if bookmark:
            self.canv.bookmarkPage(bookmark)
            self.canv.addOutlineEntry(flowable.getPlainText(), bookmark, level=0, closed=False)


def footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.line(42, 37, A4[0]-42, 37)
    canvas.setFont("Library", 7.3)
    canvas.setFillColor(colors.HexColor("#526277"))
    canvas.drawString(42, 24, f"TOPORIA  |  {BRANCH}  |  {STAMP}")
    canvas.drawRightString(A4[0]-42, 24, str(document.page))
    canvas.restoreState()


def build(output=OUTPUT):
    configure_fonts()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Body", fontName="Library", fontSize=9.5, leading=13.5, textColor=INK, spaceAfter=8))
    styles.add(ParagraphStyle("Small", parent=styles["Body"], fontSize=8, leading=11, spaceAfter=6))
    styles.add(ParagraphStyle("Section", parent=styles["Body"], fontName="Library-Bold", fontSize=19, leading=24,
                              spaceBefore=8, spaceAfter=13, keepWithNext=True))
    styles.add(ParagraphStyle("Subsection", parent=styles["Section"], fontSize=11, leading=15, spaceBefore=14, spaceAfter=7))
    styles.add(ParagraphStyle("Cell", parent=styles["Body"], fontSize=8.3, leading=11.4, spaceAfter=0,
                              splitLongWords=True, alignment=TA_LEFT))
    styles.add(ParagraphStyle("CellHead", parent=styles["Cell"], fontName="Library-Bold", fontSize=8, leading=11))
    styles.add(ParagraphStyle("Cover", parent=styles["Section"], fontSize=34, leading=40, spaceAfter=20))
    styles.add(ParagraphStyle("Kicker", parent=styles["Small"], textColor=BLUE, fontName="Library-Bold", spaceAfter=20))
    styles.add(ParagraphStyle("Metric", parent=styles["Body"], fontName="Library-Bold", fontSize=28, leading=35))
    story = []

    def p(text, style="Body"):
        item = Paragraph(inline(text), styles[style])
        story.append(item)
        return item

    def heading(text, bookmark=None):
        item = p(text, "Section")
        item.bookmark = bookmark
        story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=12))

    def table(rows, widths):
        data = [[Paragraph(inline(cell), styles["CellHead" if i == 0 else "Cell"])
                 for cell in row] for i, row in enumerate(rows)]
        result = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        result.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), PALE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8faff")]),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#9cb7df")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.35, RULE),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(result)
        story.append(Spacer(1, 9))

    p("TOPORIA / TOPOLOGY OPTIMISATION", "Kicker")
    story.append(Spacer(1, 36))
    p("The library", "Cover")
    p("What is implemented,<br/>what changed,<br/>and what remains", "Section")
    story.append(Spacer(1, 16))
    p("A linked catalogue of the current integration checkout, updated with the work completed through minimum-length constraints.")
    story.append(Spacer(1, 22))
    metrics = Table([[Paragraph(n, styles["Metric"]) for n in ("82", "8", "17")],
                     [Paragraph(label, styles["Small"]) for label in
                      ("selectable plugins", "physics engines", "benchmark presets")]], colWidths=[WIDTH/3]*3)
    metrics.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE),
                                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                                ("TOPPADDING", (0, 0), (-1, 0), 10),
                                ("BOTTOMPADDING", (0, 1), (-1, 1), 10)]))
    story.append(metrics)
    story.append(Spacer(1, 12))
    p("107 implementations in total. The 11 models and 23 updaters form 253 named compositions, plus three whole methods: 256 method names.", "Small")
    story.append(Spacer(1, 20))
    p(f"**{STAMP}**<br/>Branch `{BRANCH}` / implementation checkpoint `9abc824`", "Body")
    p("[Completed work](#completed)  /  [Current catalogue](#catalogue)  /  [Remaining work](#remaining)")
    p("Work is isolated in the integration checkout. The GUI and launcher source checkouts are unchanged; the owner reviews and merges later.", "Small")
    p("Paper and repository links are clickable. Source-code links target integration/physics; newly committed files may require the local checkout until the branch is pushed. This document does not publish or merge code.", "Small")
    story.append(PageBreak())

    heading("Completed integration work", "completed")
    p("The small and medium lists from the original PDF define this round. Existing physics was stabilised and checked before new methods were added. Each row below has its own commit; restricted variants are identified explicitly.")
    completed = [
        ("Existing physics stabilised", "Repaired compatible compositions, scaling, constraint guards and numerical issues. Existing thermal, dynamic and nonlinear physics remain in the catalogue.", "2dc42a1"),
        ("Q4 linearised buckling", "Recovered and validated the eigenproblem, complete adjoint and column benchmark; sparse solution and deterministic mode handling.", "b9f7a7f"),
        ("Anisotropic Helmholtz filter", "Conservative 2-D/3-D finite-volume filter with directional radii, preserved constants/volume and an exact adjoint.", "ce9f4e2"),
        ("Moving morphable voids", "Restricted 2-D superelliptical voids through the MMC kernel. No 3-D B-spline surfaces or FE pruning.", "6a10f2b"),
        ("Floating projection", "Updater with mass-preserving threshold, fixed-region/bound handling and internal beta continuation. The original backlog's 'without beta continuation' description is corrected.", "00ffa9b"),
        ("Annealing evaluation", "Own bounded standard-SA experiment; not an adaptive topASA port. It missed the unchanged 10%-of-OC gate on three seeds at 200 and 2000 solves and is not registered.", "8116acf"),
    ]

    def completed_table(items):
        rows = [["Addition", "Implemented scope / result", "Commit"]]
        rows.extend([[name, description, f"[{commit}]({REPOSITORY}/commit/{commit})"]
                     for name, description, commit in items])
        table(rows, [106, WIDTH-165, 59])

    completed_table(completed)
    p("These are independently implemented paper variants unless the catalogue explicitly identifies a port or an external-package wrapper. No original code was copied where reuse permission was unclear.", "Small")
    story.append(PageBreak())
    heading("Completed work / continued")
    completed_table([
        ("Compliant mechanisms", "Physical input/output ground springs, signed output-displacement adjoint, a dedicated Q4 model and Force Inverter preset; pyMOTO cross-check.", "4496e90"),
        ("Geometry projection", "Independent 2-D/3-D fixed-radius capsule bars with endpoint and activation variables, bounded union and complete derivatives; no GPTO code copied.", "55c019e"),
        ("Reaction-diffusion level set", "Sparse cell-centred 2-D compliance method using the paper's elastic topological-sensitivity tensor, an implicit PDE step and updated-volume control.", "c76509f"),
        ("Hamilton-Jacobi level set", "Godunov evolution with circular-hole plane-stress sensitivity, hole nucleation, reinitialisation and volume feedback. Not a standalone Amstutz geodesic solver.", "a27b13b"),
        ("Phase-field energy", "2-D/3-D regularised-compliance objective with a physical diffuse-interface energy and exact derivatives. Uses existing optimisers; no dedicated Allen-Cahn/Cahn-Hilliard solver.", "71abd18"),
        ("Geometric minimum length", "Solid and void constraints through a separate cone filter, complete adjoint, conservative nodal KS and fixed 1-D tolerance calibration. Not an exact geometric size certificate.", "9abc824"),
    ])
    p("**Validation checkpoint**", "Subsection")
    p("The latest full native run took 28 min 13 sec: **2303 passed, one optional multigrid skip and one outdated capability assertion failed**. Only that expected capability tuple was corrected; all six tests in its file passed on rerun. All **2304 current tests have passing coverage** across those runs. The original full-run log is retained, rather than described as a clean monolithic run.", "Small")
    p("The new methods have gradient, physical/geometric fixture and composed-run checks. GUI reachability, original golden checks, Ruff and whitespace checks pass. Original Q4/H8 sources and golden baselines are unchanged. MATLAB/Octave reference runs remain optional and have not been claimed as completed.", "Small")
    p("**Minimum-length limitation:** uniform gray starts stalled or retained violations in tested strict two-phase runs. A resolved feasible-seed cantilever with linear ersatz improved compliance from 115.115877 to 111.907874 at volume 0.5; fresh solid/void residuals were -2.22e-7 / -3.23e-8. This is a modest local validation, not evidence of reliable topology creation from a uniform start.", "Small")
    p("[Detailed integration record](../../docs/INTEGRATION-progress.md) / [Reproducible validation recipes](../../experiments/README.md)", "Small")
    story.append(PageBreak())

    heading("The current catalogue", "catalogue")
    p("The following tables are generated from `toporia/plugins/LIBRARY.md`. They include the new entries and the already implemented physics. Source and paper references retain their clickable links. Optional packages remain separate dependencies.")
    p("**Port**: translated from named code. **Paper**: independently written from a paper. **Wraps**: calls an optional external package. **Own**: Toporia's own implementation or standard practice.", "Small")
    text = (ROOT / "toporia/plugins/LIBRARY.md").read_text(encoding="utf-8")
    start = text.index("### Design representations")
    lines = text[start:].splitlines()
    i = 0
    paragraph = []

    def flush():
        if paragraph:
            p(" ".join(paragraph), "Small")
            paragraph.clear()

    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                    rows.append(cells)
                i += 1
            columns = len(rows[0])
            widths = ([109, 78, 96, 37, WIDTH-320] if columns == 5 else
                      [118, 61, 202, WIDTH-381] if columns == 4 else
                      [128, 170, WIDTH-298] if columns == 3 else [WIDTH*0.40, WIDTH*0.60])
            table(rows, widths)
            continue
        if line.startswith("## "):
            flush()
            title = line[3:]
            if title == "To add next":
                story.append(PageBreak())
                heading("Remaining work", "remaining")
                p("**Current linear sequence:** machining accessibility, projection-based self-support, multiresolution meshes, then neural reparameterisation (subject to dependency support). Machining has no code changes yet: a readable full-text copy of Langelaar (2019) is needed after institutional-download failures.", "Small")
                p("The original scope PDF remains unchanged. MATLAB/Octave oracles are optional; SINH/Hashin-Shtrikman and large framework work remain outside this agreed round.", "Small")
            else:
                p("Historical runtime blockers" if title == "Blocked for now" else title, "Subsection")
                if title == "Blocked for now":
                    p("These runtime statements are retained from the original 24 October survey; package availability was not rechecked for this PDF update.", "Small")
        elif line.startswith("### "):
            flush()
            if line.startswith("### Large:"):
                story.append(PageBreak())
                heading("Beyond this round")
                p("The original long-term research map is retained below. These larger framework changes and runtime blockers were not implemented in this integration round.", "Small")
            title = line[4:]
            p("Historical runtime blockers" if title == "Blocked for now" else title, "Subsection")
            if title == "Blocked for now":
                p("These runtime statements are retained from the original 24 October survey; package availability was not rechecked for this PDF update.", "Small")
        elif not line or line == "---":
            flush()
        else:
            paragraph.append(line.removeprefix("- "))
        i += 1
    flush()
    p("References retained from the original scope", "Subsection")
    p("[Amstutz & Andra (2006)](https://doi.org/10.1016/j.jcp.2005.12.015): standalone geodesic topological-gradient algorithms remain a candidate; the implemented HJ/TD variant is described in the catalogue. [NLopt documentation](https://nlopt.readthedocs.io/) remains the upstream guide for its wrapped optimisers.", "Small")
    doc = LibraryDocument(str(output), pagesize=A4, rightMargin=42, leftMargin=42,
                          topMargin=43, bottomMargin=52, title="Toporia library - integration update, 26 October 2026",
                          author="Toporia", subject="Linked catalogue and completed integration work through 9abc824")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    build(parser.parse_args().output)
