# apps/gui/preview.py — the problem drawn before anything is solved.
#
# Like a slicer that shows the part on the build plate before slicing, the
# view shows the problem as it is set up: the design domain, the holes and
# their solid rings, areas forced full or empty, the supports, and the loads
# of every load case as arrows.  It is drawn from the Scenario alone, so what
# is seen is exactly what a run will be given.
#
#     ┌──────────────────────────────┐
#     │▌ supports      ○ hole  ↓ F   │   blue: supports    red: loads
#     │▌                             │   grey: forced solid
#     └──────────────────────────────┘   hatched: forced empty
#
# Nothing here imports Qt: draw_problem() takes a matplotlib axis.

import math

from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch, Polygon, Rectangle

SUPPORT = "#1f77b4"
LOAD = "#d62728"
SOLID = "#7f7f7f"

_DOF_TEXT = {"both": "clamped", "x": "x fixed", "y": "y fixed"}


def supports_and_loads(scenario):
    """The supports and load points a run will use, with the problem builder's fallback.

    Returns (edges, points, loads): [(edge, dof)], [(x, y, dof)], [(x, y)].  A
    scenario with no hard supports or positive springs is clamped on its left edge, and one with
    no load points is loaded at mid-height of its right edge — as framework/problem/mesh.py does.
    """
    edges = [(c.edge, c.dof) for c in scenario.edge_constraints]
    points = [(c.x, c.y, c.dof) for c in scenario.point_constraints]
    points += [(h.cx, h.cy, "both") for h in scenario.holes if h.kind == "fixed"]
    loads = [(p.x, p.y) for p in scenario.point_loads] + [(h.cx, h.cy) for h in scenario.holes if h.kind == "load"]
    if not edges and not points and not any(s.stiffness > 0 for s in scenario.point_springs):
        edges = [("left", "both")]
    if not loads:
        loads = [(scenario.Lx, scenario.Ly / 2)]
    return edges, points, loads


def draw_problem(ax, scenario, text_colour="#222", title=""):
    """Draw `scenario` on the matplotlib axis `ax`, with a legend; returns the legend's labels."""
    Lx, Ly = scenario.Lx, scenario.Ly
    size = max(Lx, Ly)
    ax.add_patch(Rectangle((0, 0), Lx, Ly, facecolor="none", edgecolor=text_colour, linewidth=1.2))
    legend = {}

    for area in scenario.enforced_areas:
        full = area.kind == "full"
        ax.add_patch(Polygon(area.points, closed=True, facecolor=SOLID if full else "none",
                             edgecolor=SOLID, hatch=None if full else "///", alpha=0.6 if full else 1.0))
        legend["Forced solid" if full else "Forced empty"] = Patch(
            facecolor=SOLID if full else "none", edgecolor=SOLID, hatch=None if full else "///")

    for hole in scenario.holes:
        ring = {"fixed": SUPPORT, "load": LOAD}.get(hole.kind, SOLID)
        ax.add_patch(Circle((hole.cx, hole.cy), hole.r_passive, facecolor=ring, alpha=0.45, edgecolor=ring))
        ax.add_patch(Circle((hole.cx, hole.cy), hole.r_void, facecolor=ax.get_facecolor(), edgecolor=ring))
        legend["Hole with a solid ring"] = Patch(facecolor=SOLID, alpha=0.45, edgecolor=SOLID)

    edges, points, loads = supports_and_loads(scenario)
    ends = {"left": ((0, 0), (0, Ly)), "right": ((Lx, 0), (Lx, Ly)),
            "bottom": ((0, 0), (Lx, 0)), "top": ((0, Ly), (Lx, Ly))}
    for edge, dof in edges:
        (x0, y0), (x1, y1) = ends[edge]
        ax.plot([x0, x1], [y0, y1], color=SUPPORT, linewidth=5, solid_capstyle="butt")
        tx, ty = (x0 + x1) / 2, (y0 + y1) / 2
        offset = 0.03 * size
        shift = {"left": (-offset, 0), "right": (offset, 0), "bottom": (0, -offset), "top": (0, offset)}[edge]
        ax.text(tx + shift[0], ty + shift[1], _DOF_TEXT.get(dof, dof), color=SUPPORT, fontsize=8,
                ha="right" if edge == "left" else "left" if edge == "right" else "center",
                va="center", rotation=90 if edge in ("left", "right") else 0)
    for x, y, dof in points:
        ax.plot([x], [y], marker="^", markersize=9, color=SUPPORT, linestyle="none")
        ax.text(x, y - 0.04 * size, _DOF_TEXT.get(dof, dof), color=SUPPORT, fontsize=7, ha="center", va="top")
    if edges or points:
        legend["Support"] = Line2D([], [], color=SUPPORT, linewidth=4)

    length = 0.14 * size
    cases = scenario.load_cases or []
    for k, case in enumerate(cases):
        angle = math.radians(case.Fa)
        dx, dy = length * math.cos(angle), length * math.sin(angle)
        shade = 1.0 - 0.5 * k / max(len(cases) - 1, 1)
        for i, (x, y) in enumerate(loads):
            ax.annotate("", xy=(x + dx, y + dy), xytext=(x, y),
                        arrowprops=dict(arrowstyle="-|>", color=LOAD, alpha=shade, linewidth=1.6))
            if len(cases) > 1 and i == 0:   # each case named once, at its first load point
                ax.text(x + 1.15 * dx, y + 1.15 * dy, f"LC{k + 1}", color=LOAD, alpha=shade, fontsize=7,
                        ha="center", va="center")
    for x, y in loads:
        ax.plot([x], [y], marker="o", markersize=4, color=LOAD, linestyle="none")
    legend["Load" if len(cases) <= 1 else f"Loads ({len(cases)} cases)"] = Line2D(
        [], [], color=LOAD, marker=">", linewidth=1.6)

    for spring in scenario.point_springs:
        colour = "#27803e"
        horizontal = spring.dof == "x"
        coord, extent = (spring.x, Lx) if horizontal else (spring.y, Ly)
        sign = 1 if coord >= 0.5 * extent else -1
        distance = sign * 0.10 * size
        along = [distance * i / 10 for i in range(11)]
        across = [0 if i in (0, 10) else (-1) ** i * 0.012 * size for i in range(11)]
        xs = [spring.x + (a if horizontal else b) for a, b in zip(along, across, strict=True)]
        ys = [spring.y + (b if horizontal else a) for a, b in zip(along, across, strict=True)]
        ax.plot(xs, ys, color=colour, linewidth=1.2)
        ax.text(xs[-1], ys[-1] + 0.025 * size, f"k={spring.stiffness:g}",
                color=colour, fontsize=7, ha="center")
        legend["Ground spring"] = Line2D([], [], color=colour, linewidth=1.2)

    if scenario.objective.get("type") == "output_displacement":
        x, y = scenario.objective.get("x", 60.0), scenario.objective.get("y", 10.0)
        angle = math.radians(scenario.objective.get("angle", 180.0))
        ax.annotate("", xy=(x + length * math.cos(angle), y + length * math.sin(angle)), xytext=(x, y),
                    arrowprops=dict(arrowstyle="-|>", color="#8c3fb0", linewidth=1.8))
        legend["Desired output"] = Line2D([], [], color="#8c3fb0", marker="<", linewidth=1.8)

    pad = 0.2 * size
    ax.set_xlim(-pad, Lx + pad)
    ax.set_ylim(-pad, Ly + pad)
    ax.set_aspect("equal")
    ax.axis("off")
    if title:
        ax.set_title(title, color=text_colour, fontsize=10)
    ax.legend(legend.values(), legend.keys(), loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=len(legend),
              frameon=False, fontsize=8, labelcolor=text_colour)
    return list(legend)


def describe_problem(scenario, m, name=""):
    """One line under the drawing: the domain, the mesh and the material budget."""
    nx, ny = int(round(scenario.Lx * m)), max(1, int(round(scenario.Ly * m)))   # as framework/problem/mesh.py
    size = f"{scenario.Lx:g} × {scenario.Ly:g}" + (f" × {scenario.Lz:g}" if scenario.Lz > 0 else "") + " mm"
    if scenario.Lz > 0:
        nz = max(1, int(round(scenario.Lz * m)))
        mesh = f"{nx} × {ny} × {nz} = {nx * ny * nz:,} elements"
    else:
        mesh = f"{nx} × {ny} = {nx * ny:,} elements"
    prefix = f"{name}:  " if name else ""
    return f"{prefix}{size},  {mesh},  {scenario.volfrac:.0%} material"
