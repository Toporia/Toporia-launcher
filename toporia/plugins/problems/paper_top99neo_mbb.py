"""Ferrari & Sigmund (2020) Table 2: the 300 x 100 half-MBB beam of top99neo, case T3."""

from dataclasses import replace

from . import mbb_beam
from ._research import Equation, ResearchDescription

NAME = "Paper: top99neo Table 2 T3 (MBB)"
ORDER = 203
PAPER = "https://arxiv.org/abs/2005.05436"
ABOUT = ("The 300 x 100 half-MBB beam of Ferrari & Sigmund's top99neo (2020), Table 2 case T3: a density filter, "
         "a projection whose threshold keeps the volume, and beta raised by 2 every 25 steps from step 250.")
REFERENCE = ('F. Ferrari, O. Sigmund, "A new generation 99 line Matlab code for compliance topology optimization '
             'and its extension to 3D", Struct. Multidisc. Optim. 62 (2020) 2211-2228. Papers: ' + PAPER)

#: The three Table 2 cases without Anderson acceleration (T4 is T2 on a finer mesh).
CASES = ("T1", "T2", "T3")


def recipe(case):
    """(scenario, solver) of one Table 2 case: 300 x 100 elements, f = 0.5, rmin = 8.75, 2500 steps."""
    if case not in CASES:
        raise ValueError(f"unknown top99neo case {case!r}; choose one of {CASES}")
    scenario = replace(mbb_beam.scenario(), E0=1., Emin=1e-9, nu=.3)
    filters = [{"type": "density", "rmin": 8.75}]
    schedules = []
    if case != "T1":
        # ft = 3: eta chosen every step so the projection keeps the volume; beta fixed at 2 (T2).
        filters.append({"type": "heaviside", "beta": 2., "beta_max": 2., "eta_mode": "volume_preserving"})
    if case == "T3":
        # betaCnt = {250, 16, 25, 2}: +2 every 25 steps from step 250, up to 16.
        schedules.append({"path": "filters[1].beta", "type": "steps", "start": 2., "end": 16., "step": 2.,
                          "every": 25, "first": 250})
    # The paper stops on a change below 1e-6, which these runs never reach: all of them take the 2500 steps.
    solver = replace(mbb_beam.solver(), m=5., filter_specs=filters, schedules=schedules, max_iter=2500, tol=0.,
                     method_params={"move": .2}, interpolation={"type": "simp", "penal": 3.})
    return scenario, solver


def scenario():
    return recipe("T3")[0]


def solver():
    return recipe("T3")[1]


DESCRIPTION = ResearchDescription(
    question="Do Toporia's density filter, volume-preserving projection and step continuation reach the compliance "
             "top99neo reports for the same beam?",
    setup="Domain: 300 x 100 square Q4 plane-stress elements, E0 = 1, Emin = 1e-9, Poisson ratio 0.3, half-MBB "
          "supports, unit load at the top-left node. Volume 50 %, SIMP p = 3, density filter rmin = 8.75 elements, "
          "OC with move 0.2 (the paper leaves the move to the caller). 2500 steps.\n"
          "T1: density filter only. T2: plus a Heaviside projection at beta 2 whose threshold keeps the volume. "
          "T3 (this preset): T2 with beta raised by 2 every 25 steps from step 250 to 16.",
    computes="Each step filters the design, projects it with the threshold eta solved so the mean density stays at "
             "50 %, solves the equilibrium, and moves the design by optimality criteria. In T3 a steps schedule "
             "sharpens the projection from step 250 on.",
    equations=(
        Equation(r"\tilde x=Hx,\quad \bar x=\frac{\tanh(\beta\eta)+\tanh(\beta(\tilde x-\eta))}{\tanh(\beta\eta)+\tanh(\beta(1-\eta))}",
                 "Density filter, then the smoothed Heaviside projection."),
        Equation(r"\frac{1}{N}\sum_e\bar x_e(\eta)=\frac{1}{N}\sum_e\tilde x_e",
                 "The threshold eta is solved every step so that projecting does not change the volume."),
        Equation(r"\beta_k=\min\left(16,\,2+2\left\lfloor\frac{k-250}{25}+1\right\rfloor\right),\ k\geq 250",
                 "T3's continuation: beta is raised by 2 every 25 steps from step 250."),
    ),
    symbols="x: design variables; H: density filter; x tilde/bar: filtered and projected densities; beta: projection "
            "sharpness; eta: threshold; N: element count; k: step.",
    source_url=PAPER,
    figure="Ferrari & Sigmund (2020), Table 2: T1 c = 252.7, T2 c = 246.1, T3 c = 199.6 after 2500 steps.",
    comparison="experiments/research_papers.py runs T1, T2 and T3 and compares the final compliance with Table 2 "
               "(evidence in docs/research/evidence/papers). The paper's filter mirrors the design at the domain edge "
               "('N'); Toporia's density filter truncates and renormalises its weights there, as top88 does.",
    limitations="A different filter edge rule and an unstated move limit mean small differences are expected; the "
                "paper's own Anderson-accelerated runs differ from the plain ones by 1-3 %, so the problem has close "
                "local minima. 2500 steps on 30 000 elements take a while.",
    reproduce="python -m experiments.research_papers --case top99neo_t3",
    functions=("filter:density", "filter:heaviside", "schedule:steps", "updater:oc", "model:q4",
               "physics:q4_plane_stress", "representation:element_density", "interpolation:simp",
               "response:compliance"),
)
