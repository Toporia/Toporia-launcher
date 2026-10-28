"""Biyikli & To (2015) Figure 3: the half-MBB beam with the original PTOc, reproduced exactly."""

from dataclasses import replace

from toporia.framework import LoadCase, PointConstraint, PointLoad

from . import mbb_beam
from ._research import Equation, ResearchDescription

NAME = "Paper: PTOc Fig. 3 (MBB)"
ORDER = 202
PAPER = "https://doi.org/10.1371/journal.pone.0145041"
ABOUT = ("The 120 x 40 half-MBB beam of Biyikli & To (2015) Figure 3, optimised with the original proportional "
         "topology optimisation (PTOc): no sensitivities, material handed out in proportion to element compliance.")
REFERENCE = ('E. Biyikli, A. C. To, "Proportional topology optimization: a new non-sensitivity method for solving '
             'stress constrained and minimum compliance problems and its implementation in MATLAB", PLoS ONE 10 (2015) '
             'e0145041. Papers: ' + PAPER)
DESCRIPTION = ResearchDescription(
    question="Can a design method without any sensitivity analysis find a stiff layout, and does Toporia's PTOc "
             "reproduce the authors' own code step for step?",
    setup="Domain: 120 x 40 unit square Q4 elements, plane stress, E0 = 1, Emin = 1e-9, Poisson ratio 0.3.\n"
          "Supports: left edge fixed in x (symmetry); the three bottom-right nodes fixed in y.\n"
          "Load: 1 downwards, split equally over the three top-left nodes.\n"
          "Material: SIMP with exponent 3. Volume budget: 35%.\n"
          "PTOc: exponent q = 1, history weight alpha = 0.5, its own filter of radius 1.5 elements on each "
          "allocated increment, no filter chain. Stops when the largest density change drops below 0.01.",
    computes="Each iteration solves the equilibrium, takes every element's compliance, and hands the whole material "
             "budget out again in proportion to it: the allocation is filtered, capped at 1, and whatever could not be "
             "placed is handed out again until less than 0.001 remains. The new design is the average of the old one "
             "and this allocation. The element compliance is read exactly from the compliance gradient through the "
             "material law; nothing else of the gradient is used.",
    equations=(
        Equation(r"K(x)u=F,\quad c_e=E(x_e)\,u_e^{\mathsf{T}}k_0u_e,\quad E(x)=E_{\min}+(E_0-E_{\min})x^3",
                 "Equilibrium and each element's share of the compliance; their sum is the total compliance C."),
        Equation(r"x^{\rm opt}\leftarrow\mathrm{clip}\left(x^{\rm opt}+H\left(R\,\frac{c^q}{\sum_jc_j^q}\right),"
                 r"\,x_{\min},\,1\right),\quad R=V^*-\sum_ex^{\rm opt}_e",
                 "The remaining material R is distributed in proportion to compliance, smoothed by the filter H and "
                 "capped; repeated until R < 0.001."),
        Equation(r"x^{k+1}=\alpha x^k+(1-\alpha)x^{\rm opt},\quad H_{ij}=\frac{\max(0,r-d_{ij})}{\sum_k\max(0,r-d_{ik})}",
                 "The history blend damps the fixed-point iteration; H is PTOc's linear-cone filter, normalised per element."),
    ),
    symbols="x: element densities; u/F: displacement and load; k0: unit element stiffness; c_e: element compliance; "
            "q: allocation exponent; V*: material budget (0.35 x 4800); R: material still to place; H: filter; "
            "d_ij: centre distance in elements; r: filter radius; alpha: history weight; x_min = 1e-9.",
    source_url=PAPER,
    figure="Biyikli & To (2015), Figure 3, half-MBB PTOc design and compliance history.",
    comparison="The authors' unchanged PTOc_mbb.m (PLOS S2, SHA-256 recorded) was run in MATLAB R2026a: 170 printed "
               "lines, final compliance 266.61. Toporia stops after the same 169 updates; all 169 printed compliances "
               "agree to their two printed decimals and the final density agrees to 1e-8 "
               "(tests/plugins/test_ptoc.py). This is a native-code match, not only a visual one.",
    limitations="PTOc is a heuristic fixed-point method with no convergence theory and compliance only. It reaches "
                "266.61, while sensitivity-based methods find stiffer designs on comparable settings. The separate "
                "'pto' updater is a different, sensitivity-proxy variant.",
    reproduce='toporia run "Paper: PTOc Fig. 3 (MBB)"',
    functions=("updater:ptoc", "model:q4", "physics:q4_plane_stress", "representation:element_density",
               "interpolation:simp", "response:compliance"),
)


def scenario():
    return replace(mbb_beam.scenario(), Lx=120., Ly=40., volfrac=.35, E0=1., Emin=1e-9, nu=.3,
                   point_loads=[PointLoad(x=float(x), y=40.) for x in range(3)],
                   load_cases=[LoadCase(Fmag=1 / 3, Fa=270.)],
                   point_constraints=[PointConstraint(x=120., y=float(y), dof="y") for y in range(3)])


def solver():
    return replace(mbb_beam.solver(), method="q4+ptoc", method_params={}, filter_specs=[], m=1.,
                   interpolation={"type": "simp", "penal": 3.}, max_iter=600, tol=.01)
