"""Render structured research explanations as portable HTML with typeset equations.

MathText produces embedded PNGs locally: no browser scripts, network, TeX install,
temporary-file lifetime, or raw LaTeX in the GUI. Data remains GUI-independent.
"""

import base64
import html
from functools import lru_cache
from io import BytesIO


@lru_cache(maxsize=256)
def equation_image(latex):
    from matplotlib import rc_context
    from matplotlib.font_manager import FontProperties
    from matplotlib.mathtext import math_to_image
    from PIL import Image

    buffer = BytesIO()
    with rc_context({"text.usetex": False, "mathtext.fontset": "dejavusans"}):
        math_to_image("$" + " ".join(latex.split()) + "$", buffer,
                      prop=FontProperties(family="DejaVu Sans", size=14),
                      dpi=180, format="png", color="#142338")
    raw = buffer.getvalue()
    with Image.open(BytesIO(raw)) as rendered:
        width, height = rendered.size
    # 2.5 physical pixels per logical pixel: sharp on high-DPI screens.
    scale = min(.4, 430 / width)
    return base64.b64encode(raw).decode("ascii"), max(1, round(width * scale)), max(1, round(height * scale))


def description_html(description):
    """A QTextBrowser-compatible HTML fragment; all contributor text is escaped."""
    escape = html.escape
    sections = [
        ("Question", description.question),
        ("Setup", description.setup),
        ("How the function computes", description.computes),
    ]
    rows = [f"<p><b>{title}</b><br>{escape(text)}</p>" for title, text in sections]
    rows.append("<p><b>Mathematics</b></p>")
    for equation in description.equations:
        data, width, height = equation_image(equation.latex)
        alt = escape(equation.explanation, quote=True)
        rows.append(f'<table bgcolor="#ffffff" cellpadding="8"><tr><td>'
                    f'<img src="data:image/png;base64,{data}" width="{width}" height="{height}" alt="{alt}">'
                    f'</td></tr></table><p>{escape(equation.explanation)}</p>')
    for title, text in (
        ("Symbols and units", description.symbols),
        ("Research target", description.figure),
        ("What is compared", description.comparison),
        ("Limitations", description.limitations),
        ("Reproduce", description.reproduce),
        ("Functions demonstrated", ", ".join(description.functions)),
    ):
        rows.append(f"<p><b>{title}</b><br>{escape(text)}</p>")
    url = description.source_url
    if url.startswith(("https://", "http://")):
        rows.append(f'<p><b>Paper</b><br><a href="{escape(url, quote=True)}">{escape(url)}</a></p>')
    elif url:
        rows.append(f"<p><b>Paper</b><br>{escape(url)}</p>")
    return "\n".join(rows)


def description_page(title, description):
    """Standalone export for reading/sharing the same content outside the GUI."""
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            f'<title>{html.escape(title)}</title><style>'
            'body{font:16px/1.6 system-ui,sans-serif;color:#142338;background:#fff;'
            'max-width:880px;margin:36px auto;padding:0 24px}'
            'table{max-width:100%}img{max-width:100%;height:auto}b{color:#214e78}'
            f'</style><h1>{html.escape(title)}</h1>{description_html(description)}</html>')
