"""Hoghoj & Traff (2021) Table 2: the 200 x 100 cantilever milled from three sides (Fig. 6b)."""

from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Scenario, Solver

from ._research import Equation, ResearchDescription

NAME = "Paper: Machining Fig. 6b (cantilever)"
ORDER = 204
PAPER = "https://arxiv.org/abs/2102.12999"
ABOUT = ("The 2 x 1 cantilever of Hoghoj & Traff's advection-diffusion machining filter (2021), milled from the top "
         "and both ends (their Fig. 6b): every surface must be reachable by a tool from one of those sides.")
REFERENCE = ('L. C. Hoghoj, E. A. Traff, "An advection-diffusion based filter for machinable designs in topology '
             'optimization", Comput. Methods Appl. Mech. Engrg. 391 (2022) 114488. Papers: ' + PAPER)

#: The paper's tool angles as Toporia's tool sides: its 0 degrees is a tool reaching from +x, -90 one from below.
SIDES = {0: "pos_x", 180: "neg_x", -90: "neg_y"}


def recipe(sides):
    """(scenario, solver) for tools from the given box sides; () is the paper's unconstrained reference."""
    scenario = Scenario(Lx=60., Ly=30., edge_constraints=[EdgeConstraint("left", "both")],
                        point_loads=[PointLoad(x=60., y=0.)], load_cases=[LoadCase(Fmag=1., Fa=270.)], volfrac=.5)
    filters = [{"type": "density", "rmin": 3.}]          # radius 0.03 of the unit height: 3 elements
    if sides:
        machining = {"type": "machining", "from_pos_y": False, "power": -3., "peclet": 1e4}
        machining.update({f"from_{side}": True for side in sides})
        filters.append(machining)
        # The paper's penalties: 5 with one or two tools, 3 with more.
        penal, move = (5. if len(sides) <= 2 else 3.), .01
    else:
        # The paper's reference is a robust design; a sharpened projection stands in for it here.
        filters.append({"type": "heaviside", "beta": 1., "beta_max": 32., "beta_interval": 40})
        penal, move = 3., .2
    return scenario, Solver(method="q4+mma", m=10 / 3, filter_specs=filters, max_iter=400, tol=.001,
                            method_params={"move": move}, interpolation={"type": "simp", "penal": penal})


def scenario():
    return recipe(("neg_y", "pos_x", "neg_x"))[0]


def solver():
    return recipe(("neg_y", "pos_x", "neg_x"))[1]


DESCRIPTION = ResearchDescription(
    question="Does Toporia's machining filter cost the stiffness Hoghoj & Traff report for each set of tool directions?",
    setup="Domain: 2 x 1 cantilever on 200 x 100 Q4 elements, clamped left edge, unit downward load at the lower right "
          "corner, volume 50 %. Density filter radius 0.03 (3 elements), machining filter with Peclet number 10^4 and "
          "shadow power -3, SIMP p = 5 for one or two tools and 3 for more, MMA with move 0.01, 400 steps.\n"
          "This preset: tools from below (-90 degrees) and from both ends (0 and 180 degrees), the paper's Fig. 6b.",
    computes="Each step filters the design, then solves one advection-diffusion problem per tool side: material casts "
             "a shadow downstream of the tool, and the shadows are intersected, so a cavity no tool can reach fills up. "
             "The equilibrium and the compliance gradient follow, back through every transpose solve.",
    equations=(
        Equation(r"u_a\cdot\nabla T_a-D\nabla^2T_a=\tilde\rho/h,\quad T_*=\left(\frac{1}{n}\sum_aT_a^{p}\right)^{1/p},\ p<0",
                 "One shadow per tool side a, combined by a negative-power mean that approaches their minimum."),
        Equation(r"\frac{C}{C_{\rm ref}}", "The comparison is the compliance relative to the unconstrained reference design."),
    ),
    symbols="u_a: tool direction; D: diffusion from the Peclet number; rho tilde: filtered density; h: cell size; "
            "T_a, T_*: single and combined shadows; p: intersection power; n: tool count; C_ref: reference compliance.",
    source_url=PAPER,
    figure="Hoghoj & Traff (2021), Table 2 and Figs. 5-6: reference c = 69.98; 0 deg 2.57, 180 deg 4.11, "
           "{-90, 0} 3.15 and {-90, 0, 180} 1.24 times the reference.",
    comparison="experiments/research_papers.py runs the reference and the four axis-direction designs and compares "
               "the compliance and the ratios with Table 2 (evidence in docs/research/evidence/papers).",
    limitations="Toporia's filter handles tool sides along the axes only, so the paper's oblique tools (-30, 160 and "
                "240 degrees, and the four diagonals) are not reproduced. The paper's reference is a robust design and "
                "its MMA settings and step count are not stated; here a projection with continuation and 400 steps "
                "stand in.",
    reproduce="python -m experiments.research_papers --case machining_m90_0_180",
    functions=("filter:machining", "filter:density", "updater:mma", "model:q4", "physics:q4_plane_stress",
               "representation:element_density", "interpolation:simp", "response:compliance"),
)
