"""Plain research-description data; no GUI, plotting or solver dependencies.

Preset modules optionally declare DESCRIPTION = ResearchDescription(...).
Equations use Matplotlib's MathText subset (without surrounding dollar signs).
Text is always plain text; renderers escape it rather than trusting HTML.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Equation:
    latex: str
    explanation: str


@dataclass(frozen=True)
class ResearchDescription:
    question: str
    setup: str
    computes: str
    equations: tuple[Equation, ...]
    symbols: str
    source_url: str
    figure: str
    comparison: str
    limitations: str
    reproduce: str
    functions: tuple[str, ...]


PAPER = "https://doi.org/10.1007/s00158-010-0594-7"
AUTHOR_PDF = "https://www.topopt.mek.dtu.dk/-/media/subsites/topopt/apps/dokumenter-og-filer-til-apps/topopt88.pdf"


def top88_description(kind):
    """Shared science, explicit differences between the two Figure 3(a) panels."""
    if kind not in {"density", "sensitivity"}:
        raise ValueError(f"Unknown top88 filtering variant: {kind}")
    density = kind == "density"
    filtering = (
        Equation(r"\rho_i=\frac{\sum_j H_{ij}x_j}{\sum_j H_{ij}},\quad H_{ij}=\max(0,r_{\min}-d_{ij})",
                 "Density filtering averages nearby design variables before the stiffness solve."),
        Equation(r"\nabla_x C=H^{\mathsf{T}}(\nabla_\rho C/s),\quad s_i=\sum_j H_{ij}",
                 "The adjoint carries physical-density gradients back to design variables; division is componentwise."),
    ) if density else (
        Equation(r"H_{ij}=\max(0,r_{\min}-d_{ij}),\quad s_i=\sum_j H_{ij}",
                 "Distance weights decrease linearly to zero at the filter radius; rows are truncated at the domain boundary."),
        Equation(r"\rho=x,\quad \widehat{g}_i=\frac{\sum_j H_{ij}x_jg_j}{s_i\max(10^{-3},x_i)}",
                 "Sensitivity filtering changes the search direction, while the physical density equals the design."),
    )
    return ResearchDescription(
        question="How does spatial regularisation change the stiffest half-MBB beam under a 50% material budget?",
        setup="60 by 20 square Q4 plane-stress elements; unit thickness; left-edge horizontal symmetry support; "
              "bottom-right vertical roller; downward unit force at the top-left node. E0=1, Emin=1e-9, "
              "Poisson ratio 0.3, initial density 0.5, SIMP exponent 3, filter radius 2.4 elements, OC move 0.2. "
              "Stop at maximum design-variable change below 0.01; safety cap 200 iterations.",
        computes="Element variables feed the selected filter, SIMP stiffness, a sparse equilibrium solve, "
                 "compliance and volume sensitivities, then an optimality-criteria update. "
                 + ("Both compliance and volume gradients use the filter adjoint." if density else
                    "Only the compliance direction uses the sensitivity heuristic; the volume gradient stays exact."),
        equations=(
            Equation(r"K(\rho)u=f,\quad C=f^{\mathsf{T}}u,\quad \frac{1}{N}\sum_e\rho_e\leq 0.5",
                     "Equilibrium determines displacement; lower compliance means greater stiffness for this fixed load."),
            Equation(r"E_e=E_{\min}+(E_0-E_{\min})\rho_e^3",
                     "SIMP penalises intermediate material; the small void stiffness regularises the solve."),
            *filtering,
            Equation(r"\frac{\partial C}{\partial\rho_e}=-3(E_0-E_{\min})\rho_e^2u_e^{\mathsf{T}}K_e^0u_e",
                     "Self-adjoint compliance sensitivity uses element strain-energy contractions; no extra adjoint solve."),
            Equation(r"x_e^+=\mathrm{clip}_{[\ell_e,h_e]}\left(x_e\sqrt{\max(0,-g_e/(\lambda v_e))}\right)",
                     "OC uses bisection on lambda to meet the physical-volume budget; bounds include the 0.2 move limit."),
        ),
        symbols="x: design variables; rho: physical densities; N: element count; u and f: displacement and force; "
                "K: assembled stiffness; K_e^0: unit-modulus element stiffness; H: distance weights; d_ij: cell-centre "
                "distance; s: row sums; g: exact or sensitivity-filtered compliance direction; v: volume gradient; "
                "lambda: volume multiplier; v uses the optimizer's summed-density volume convention; "
                "ell and h: lower/upper move-and-box bounds. Normalised reference units.",
        source_url=PAPER,
        figure="Andreassen et al. (2011), Figure 3(a), " + ("bottom" if density else "top") + " panel (60 by 20). "
               "Panel location and radius checked against the author-hosted uncorrected manuscript; published values "
               "must be checked separately if a numerical figure caption is used.",
        comparison="The experiment compares final density fields, stopping count and pre-update printed compliance "
                   "against the unchanged, SHA-256-identified author top88 code on exactly this setup. "
                   "The paper-panel comparison is visual; native-code agreement is a separate numerical check.",
        limitations="A matching example is evidence for this setup, not global optimality or every pairing. "
                    "The general MBB preset uses radius 1.5 and is intentionally unchanged. Sensitivity filtering "
                    "is a heuristic, not the derivative of its identity forward map. Last printed compliance "
                    "belongs to the design before the last update; fresh final-design compliance is reported separately.",
        reproduce="Select this research preset in the GUI, or run: python -m experiments.research_figures --case " + kind,
        functions=("model:q4", "physics:q4_plane_stress", "representation:element_density", "filter:" + kind,
                   "interpolation:simp", "response:compliance", "updater:oc"),
    )
