# plugins/problems/_truss_description.py — the research description shared by the truss presets.

from ._research import Equation, ResearchDescription

EQUATIONS = (
    Equation(r"\min_a\ C=\sum_k w_k f_k^{\mathsf{T}}u_k,\quad K(a)u_k=f_k,\quad \sum_i a_iL_i\le V",
             "Minimum compliance of a pin-jointed truss: the bar areas a are the design variables and the "
             "volume budget bounds the total bar volume."),
    Equation(r"K(a)=\sum_i \frac{E a_i}{L_i}\begin{bmatrix}cc^{\mathsf{T}}&-cc^{\mathsf{T}}\-cc^{\mathsf{T}}"
             r"&cc^{\mathsf{T}}\end{bmatrix}",
             "Each bar adds an axial stiffness along its unit vector c between its two nodes."),
    Equation(r"a_i\leftarrow a_i\left(\frac{-\partial C/\partial a_i}{\lambda L_i}\right)^{1/2}",
             "The optimality-criteria update, within move limits; the multiplier lambda meets the volume "
             "budget by bisection."),
    Equation(r"\rho_e=\mathrm{clip}\left(\frac{r_i-d_{e,i}}{h}+\tfrac12,0,1\right)",
             "The settled truss is drawn as a density: every bar a capsule of radius r_i (half its area in 2-D, "
             "the radius of its cross-section in 3-D), smoothed over one element of size h."),
)


def truss_description(module, stage_text):
    """The description of a truss preset: the method, its two stages, and its limits."""
    solver = module.solver()
    params = solver.method_params
    return ResearchDescription(
        question=module.ABOUT,
        setup=(f"Ground-structure nodes every {params.get('spacing', 5.0)} mm, bars to neighbours up to "
               f"{params.get('reach', 2)} steps apart without overlapping collinear bars; the scenario's supports, "
               f"loads, E0 and volume budget; mesh resolution {solver.m} elements per mm for the continuum stage."),
        computes=("Each iteration solves the truss for every load case, takes the compliance gradient per bar and "
                  "updates the areas. When they settle, " + stage_text),
        equations=EQUATIONS,
        symbols=("a: bar areas; L: bar lengths; c: bar unit vectors; E: Young's modulus; f/u: load and displacement "
                 "per load case k with weight w; V: the volume budget; lambda: the volume multiplier; rho_e: the "
                 "density of element e; d: distance from the element centre to a bar; h: element size."),
        source_url="https://doi.org/10.1007/978-3-662-05086-6",
        figure="The bar layout of a minimum-compliance ground-structure truss.",
        comparison=("Truss compliance is not comparable with a continuum's: bars carry only axial force. Compare the "
                    "converted design's continuum compliance and peak stress, which the run records."),
        limitations=("Pin-jointed bars, linear elastic, small displacements; no buckling of slender bars; the drawing "
                     "smooths bars over one element and overlaps them at joints, so its volume differs from the "
                     "truss volume."),
        reproduce=f'toporia run "{module.NAME}"',
        functions=("method:truss", "response:compliance")
                  + (("response:peak_stress", "model:q4", "updater:mma") if params.get("stage") == "stress" else ()),
    )
