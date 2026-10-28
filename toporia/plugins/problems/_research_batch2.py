"""Batch 2 scientific descriptions and companion optimization recipes.

Transfer/constitutive figures run through experiments.research_batch2. The
ordinary GUI Run remains an optimization companion, clearly stated in help.
No algorithm, objective contract or GUI execution model is added here.
"""

from dataclasses import replace

from . import mbb_beam
from ._research import Equation, ResearchDescription

TOP88 = "https://doi.org/10.1007/s00158-010-0594-7"
WANG = "https://doi.org/10.1007/s00158-010-0602-y"
MORPH = "https://doi.org/10.1007/s00158-006-0087-x"
ORDERED = "https://doi.org/10.1007/s00158-022-03379-7"
BRUNS = "https://doi.org/10.1007/s00158-005-0537-x"
BOUNDS = "https://doi.org/10.1007/s004190050248"
#: Companions kept out of discovery because of a known numerical failure, {case: reason}.  The
#: volume-preserving projection left it once its 0/1-design limit was settled (identity when uniform,
#: an explicit error when mixed; see plugins/filters/heaviside.py).
QUARANTINED = {}


def _case(label, kind, name, spec, equations, computes, source, target, limits,
          *, schedules=(), overrides=None):
    return dict(label=label, kind=kind, function=f"{kind}:{name}", spec=spec,
                equations=tuple(Equation(*equation) for equation in equations),
                computes=computes, source=source, target=target, limits=limits,
                schedules=list(schedules), overrides=overrides or {})


CASES = {
    "pde": _case("PDE filter: top82 Fig. 4(b)", "filter", "pde", {"type": "pde", "rmin": 6.},
        [(r"-r^2\nabla^2\bar\rho+\bar\rho=x,\quad \partial_n\bar\rho=0", "Helmholtz smoothing with no boundary flux."),
         (r"\bar\rho=T^{\mathsf{T}}(r^2K_f+M_f)^{-1}Tx", "Transfer element values to nodes, solve, and transfer back."),
         (r"r=r_{\min}/(2\sqrt{3}),\quad \nabla_xJ=F^{\mathsf{T}}\nabla_{\bar\rho}J",
          "Here the discrete filter F is symmetric; the same solve is the exact adjoint.")],
        "Factorize the nodal filter matrix once and reuse it for forward and adjoint operations.",
        TOP88, "Andreassen et al. (2011), Figure 4, middle bottom density-filter panel, 150 by 50 cells, radius 6.",
        "The corrected author top82 refuses radii below 2.5; this recipe uses 6. "
        "Printed compliance is pre-update. Final-field agreement is checked after one declared vertical row conversion.",
        overrides={"m": 2.5, "max_iter": 800}),
    "pde_anisotropic": _case("Directional PDE filter", "filter", "pde_anisotropic",
        {"type": "pde_anisotropic", "rmin_x": 6., "rmin_y": 2.},
        [(r"-\nabla\cdot(D\nabla\bar\rho)+\bar\rho=x,\quad D_{aa}=r_a^2/12",
          "Axis-aligned finite-volume diffusion; different radii smooth directions differently."),
         (r"A\bar\rho=x,\quad \nabla_xJ=A^{-\mathsf{T}}\nabla_{\bar\rho}J",
          "A symmetric no-flux matrix preserves constants and the summed field.")],
        "Solve a cell-centred directional Helmholtz equation. Compare a cosine mode against its analytic Neumann solution.",
        "https://doi.org/10.1002/nme.3072", "Lazarov-Sigmund Helmholtz formulation; no matching directional finite-volume paper panel identified.",
        "Toporia's anisotropic cell-centred extension differs from the paper's nodal discretization. "
        "The generated impulse/cosine figure is an analytic verification, not a reproduced research panel."),
    "heaviside": _case("Heaviside projection curves", "filter", "heaviside",
        {"type": "heaviside", "beta": 8., "eta": .5, "beta_max": 8.},
        [(r"P(x)=\frac{\tanh(\beta\eta)+\tanh(\beta(x-\eta))}{\tanh(\beta\eta)+\tanh(\beta(1-\eta))}",
          "Threshold eta controls the transition; beta controls sharpness."),
         (r"P'(x)=\frac{\beta[1-\tanh^2(\beta(x-\eta))]}{\tanh(\beta\eta)+\tanh(\beta(1-\eta))}",
          "The pointwise derivative carries sensitivities back.")],
        "Plot the implemented tanh projection at fixed thresholds and sharpness values; compare to Wang equation (9).",
        WANG, "Wang et al. (2011), equation (9); Figure 5(f) is a separate pattern-based target.",
        "The exact Figure 5 design bitmap is not available here. The transfer curves check the published equation, "
        "but are not a reproduction of its pattern panel or evidence of minimum length-scale control."),
    "heaviside_volume": _case("Volume-preserving projection", "filter", "heaviside",
        {"type": "heaviside", "beta": 16., "beta_max": 16., "eta_mode": "volume_preserving"},
        [(r"\sum_i P(x_i,\eta(x))=\sum_i x_i", "Bisection finds a threshold that preserves the input volume."),
         (r"\frac{\partial\eta}{\partial x_j}=\frac{1-P_{x,j}}{\sum_iP_{\eta,i}}",
          "The threshold depends on every input; its derivative must be included."),
         (r"g_j=s_jP_{x,j}+\frac{\sum_i s_iP_{\eta,i}}{\sum_iP_{\eta,i}}(1-P_{x,j})",
          "The exact adjoint contains a global correction.")],
        "Compare fixed-threshold and volume-preserving projection on a nonuniform field and verify the implicit adjoint.",
        "https://doi.org/10.1007/s00158-020-02629-w",
        "Ferrari-Sigmund (2020) volume-preserving construction; exact source figure remains to select.",
        "Mean preservation does not make every cell or optimized topology agree with top99neo. "
        "The input field here is a controlled ramp, not a paper design."),
    "morphology": _case("Morphology: four operations", "filter", "morphology",
        {"type": "morphology", "mode": "open", "beta": 32., "rmin": 2.4},
        [(r"D_i(x)=\beta^{-1}\log\!\left(\sum_j w_{ij}e^{\beta x_j}\right)",
          "Normalized weights sum to one; shifted exponentials avoid overflow."),
         (r"E_i(x)=-\beta^{-1}\log\!\left(\sum_j w_{ij}e^{-\beta x_j}\right)",
          "Smooth erosion is the soft minimum."),
         (r"O=D\circ E,\quad C=E\circ D,\quad w_{ij}=H_{ij}/\sum_jH_{ij}",
          "Opening removes thin solid details; closing fills thin void details.")],
        "Apply erosion, dilation, opening and closing to the same controlled binary pattern; compare with hard morphological limits.",
        MORPH, "Sigmund (2007), Figure 3, basic morphology operations; equations (18)-(21).",
        "The paper uses a five-cell structuring element and uniform weights for its illustrative binary example. "
        "Toporia uses cone weights and finite sharpness; the recreated pattern is not the original bitmap. "
        "Opening/closing are not generally exactly volume preserving on arbitrary fields."),
    "am": _case("AM overhang filter", "filter", "am",
        {"type": "am", "direction": 0, "overhang_angle": 45.},
        [(r"s_i=\left(\sum_{j\in S_i}\rho_j^P\right)^{1/Q}", "A smooth support measure uses the preceding layer."),
         (r"Q=P+\log(N_s)/\log(\xi_0),\quad P=40,\quad \xi_0=0.5",
          "The implementation also uses tiny shifts/backshifts to regularize exact zeros; Ns is the support-stencil size."),
         (r"\rho_i=\frac{1}{2}(x_i+s_i-\sqrt{(x_i-s_i)^2+\epsilon}+\sqrt{\epsilon})",
          "A smooth minimum limits printable density; the adjoint follows dependencies through every layer.")],
        "Filter a supported pillar, overhang and floating island; record the build-direction convention and test the complete adjoint.",
        "https://doi.org/10.1007/s00158-016-1522-2",
        "Langelaar (2017), illustrative printing/filter examples; exact panel and geometry require source alignment.",
        "The field is a controlled diagnostic, not an optimized paper topology or a printability certificate. "
        "Angle stencils are discrete and display direction must be checked explicitly."),
    "symmetry": _case("Mirror symmetry", "filter", "symmetry", {"type": "symmetry", "axis": "both"},
        [(r"P=\frac{1}{2}(I+M),\quad P^2=P,\quad P^{\mathsf{T}}=P",
          "Mirror averaging is an orthogonal projection; both axes compose two commuting projections.")],
        "Show an asymmetric field before and after mirror averaging; independently check symmetry, mean and idempotence.",
        "https://doi.org/10.1007/978-3-662-05086-6",
        "Standard symmetry restriction; no specific book figure assigned to this Toporia implementation.",
        "This is an engineering operator demonstration. Symmetric density is not the same as symmetric loads or a symmetric state solution."),
    "routing": _case("Router-radius closing", "filter", "routing",
        {"type": "routing", "radius_mm": 2., "P": 20., "start_iter": 0, "ramp_iters": 1},
        [(r"\rho_i=(1-\alpha\chi_i)x_i+\alpha\chi_iE(D(\tilde{x}))_i",
          "A ramp blends closing only in the interior mask chi; the boundary band passes through."),
         (r"\tilde{x}_i=x_i\,\mathbf{1}_{x_i\geq\tau},\quad r_{\mathrm{el}}=r_{\mathrm{mm}}m",
          "The closing path first zeros sub-threshold values; the direct blend retains the original x."),
         (r"D_i(x)=\left(n_i^{-1}\sum_{j\in N_i}x_j^P\right)^{1/P},\quad E(x)=1-D(1-x)",
          "The normalized p-norm and complementary erosion differ from the exponential morphology filter; a low-density threshold is applied first.")],
        "Show narrow and wide void channels before/after the current smooth closing, with the threshold and ramp made explicit.",
        MORPH, "Inspired by Sigmund morphology; no published figure for this Toporia-specific router rule.",
        "A p-norm construction and threshold differ from the paper's exponential operators. "
        "A boundary band bypasses the operation. The volume backward pass floors sensitivity at 1e-6 "
        "for OC stability and is not the exact volume derivative where that floor is active. "
        "It is not a finite-tool accessibility or collision certificate."),
    "extrusion": _case("Constant cross-section", "filter", "extrusion", {"type": "extrusion", "axis": "y"},
        [(r"(Px)_{ij}=n_y^{-1}\sum_kx_{kj},\quad P^2=P=P^{\mathsf{T}}",
          "Average each vertical column and broadcast it back; in 3-D choose an extrusion axis.")],
        "Demonstrate constant cross-section and check the averaging projection without claiming an optimized 3-D paper shape.",
        "https://doi.org/10.1299/jsmea.47.198",
        "Ishii-Aomura (2004), constant-cross-section design; specific optimized panel not reconstructed.",
        "The diagnostic is 2-D. Reproducing a 3-D optimized paper figure also requires its loads, geometry and optimizer settings."),
    "pattern": _case("Repeated layout pattern", "filter", "pattern", {"type": "pattern", "nx": 3, "ny": 2},
        [(r"(Px)_{c,i}=n_c^{-1}\sum_d x_{d,i},\quad P^2=P=P^{\mathsf{T}}",
          "All repetitions share the averaged local-cell value; mesh counts must divide exactly.")],
        "Show six identical repeated cells and verify periodic equality and the exact adjoint.",
        "https://doi.org/10.1007/s00158-008-0332-6",
        "Almeida et al. layout-pattern restrictions; exact paper geometry/panel pending.",
        "Identical cells alone do not reproduce the paper's optimized structure; supports and loads need not repeat."),
    "casting": _case("Casting draw direction", "filter", "casting", {"type": "casting", "direction": "+y"},
        [(r"\rho_0=x_0,\quad \rho_k=\mathrm{smin}(x_k,\rho_{k-1})",
          "A cumulative smooth minimum propagates material from the parting plane."),
         (r"\mathrm{smin}(a,b)=\frac{1}{2}(a+b-\sqrt{(a-b)^2+\epsilon}+\sqrt{\epsilon})",
          "Reverse accumulation supplies the exact adjoint of the current recursion.")],
        "Show the effect of draw direction on a controlled field; measure the smooth monotonicity bound.",
        "https://doi.org/10.1007/s00158-011-0632-0",
        "Gersborg-Andreasen (2011), casting parameterization; exact formulation differs.",
        "The cited paper uses a Heaviside parameterization. This smooth running-minimum variant is not a direct reproduction; "
        "its output is only approximately monotone and does not model a full mould."),
    "machining": _case("PDE machining shadows", "filter", "machining",
        {"type": "machining", "from_pos_y": True, "peclet": 10000., "beta": 8., "eta": .4, "power": -4.},
        [(r"u\cdot\nabla T-D\nabla^2T=\rho/h", "An advection-diffusion solve casts a material shadow from each tool side."),
         (r"T_*=\left(n^{-1}\sum_a T_a^p\right)^{1/p},\quad p<0",
          "A negative-power mean intersects shadows before bounded projection.")],
        "Visualize one-sided Cartesian tool shadows and check the full transpose-solve adjoint.",
        "https://doi.org/10.1016/j.cma.2021.114488",
        "Hoghoj-Traff (2022), advection-diffusion machining; paper geometry is not reproduced by the diagnostic.",
        "Independent Cartesian cell-centred variant: no finite cutter/holder, oblique directions or forced-void regions. "
        "Projection and diffusion can leave access artifacts; no machinability certificate.",
        overrides={"method": "q4+mma", "method_params": {"move": .01}}),
    "self_support": _case("Gaynor-Guest support", "filter", "self_support",
        {"type": "self_support", "direction": "+y", "rmin": 2.4, "threshold": .1,
         "beta_support": 20., "beta_local": 35.},
        [(r"\phi_i=\psi_i H_T\!\left(\mathrm{mean}_{j\in S_i}\phi_j\right)",
          "Supported design propagates from the build plate through the lower wedge."),
         (r"H_T(s)=\frac{\tanh(bT)+\tanh(b(s-T))}{\tanh(bT)+\tanh(b(1-T))}",
          "The support gate uses threshold T and support sharpness b; the first layer is supported by the build plate."),
         (r"\mu=F_{\mathrm{cone}}\phi,\quad \rho=1-e^{-\beta\mu}+\mu e^{-\beta}",
          "A local average and exponential projection produce density; the adjoint reverses both stages and the recursion.")],
        "Show lower-wedge support gating on supported/floating features and independently check the recursive adjoint.",
        "https://doi.org/10.1007/s00158-016-1551-x",
        "Gaynor-Guest (2016), support projection; exact nodal paper panel not reproduced.",
        "Toporia uses cell centres and a grid-dependent threshold; the paper's nodal examples and this controlled pattern differ. "
        "A smooth supported field does not certify a binary design, exact angle or material budget.",
        overrides={"method": "q4+mma", "method_params": {"move": .01},
                   "interpolation": {"type": "ramp", "q": 10.}}),
    "ramp": _case("RAMP stiffness curves", "interpolation", "ramp", {"type": "ramp", "q": 8.},
        [(r"E=E_{\min}+(E_0-E_{\min})\frac{\rho}{1+q(1-\rho)}", "Rational penalization has a nonzero slope at void."),
         (r"E'=(E_0-E_{\min})\frac{1+q}{[1+q(1-\rho)]^2}", "The derivative drives physical sensitivities.")],
        "Plot stiffness and slope for q=0,1,5,20 and compare with independent rational evaluations.",
        "https://doi.org/10.1007/s001580100129",
        "Stolpe-Svanberg (2001); original figure/parameter set not available in this source review.",
        "The q values are declared demonstration choices. Equation agreement is not agreement with a numbered paper figure."),
    "ordered_simp": _case("Ordered SIMP: formula audit", "interpolation", "ordered_simp",
        {"type": "ordered_simp", "n_materials": 4, "rho2": .4, "rho3": .6, "E2": .5, "E3": .7, "penal": 3.},
        [(r"t=\frac{\rho-\rho_i}{\rho_{i+1}-\rho_i},\quad f=f_i+(f_{i+1}-f_i)t^p",
          "Toporia uses interval-local penalization: the increasing-material branch of the 2022 modified formulation."),
         (r"f_{\mathrm{original}}=A_i\rho^p+B_i",
          "The original 2017 expression scales the global power; it is generally different above the first interval.")],
        "Recreate the modified curves in da Silveira-Palma Figure 1 at p=1,3,5 and overlay the original formula to expose the attribution difference.",
        ORDERED, "da Silveira-Palma (2022), Figure 1 modified curves, Table 1; compare original equations (2)-(3) separately.",
        "This verifies stiffness interpolation only, with 1e-8 absolute tolerance for the finite soft phase. "
        "No cost interpolation, non-monotone moduli, optimizer trajectory or paper bridge design is claimed.",
        overrides={"method": "q4+mma"}),
    "sinh": _case("SINH effective-cost curves", "interpolation", "sinh", {"type": "sinh", "penal": 3.1},
        [(r"\eta_1=\rho,\quad \eta_2=1-\frac{\sinh(p(1-\rho))}{\sinh p}",
          "Stiffness is linear; intermediate density is penalized through effective material cost."),
         (r"\eta_2'=\frac{p\cosh(p(1-\rho))}{\sinh p}", "The volume adjoint uses this slope, not one.")],
        "Recreate Bruns Figure 4: the linear first measure and second measures for p=1.1,2.1,3.1,4.1,5.1.",
        BRUNS, "Bruns (2005), Figure 4, equations (22)-(23).",
        "A constitutive/cost-curve reproduction does not reproduce the separate resource-filter case-6 topology. "
        "Toporia's companion optimization shares one filtered field between both measures.",
        overrides={"method": "q4+mma", "method_params": {"move": .05}}),
    "hashin_shtrikman": _case("SIMP and HS envelope", "interpolation", "hashin_shtrikman", {"type": "hashin_shtrikman"},
        [(r"E_{\mathrm{HS}}/E_0=\rho/(3-2\rho),\quad \nu=1/3,\quad E_{\min}=0",
          "The 2-D fixed-Poisson elastic ray has this solid-void upper envelope; Figure 2 compares it with rho squared and cubed."),
         (r"E=E_{\min}+(E_0-E_{\min})\rho/[1+q(1-\rho)]",
          "The implemented general envelope uses the stricter bulk/shear bound and binds dimension and Poisson ratio from the scenario.")],
        "Recreate the constitutive curves of Bendsoe-Sigmund Figure 2 at nu=1/3; independently test the rational envelope and SIMP curves.",
        BOUNDS, "Bendsoe-Sigmund (1999), Figure 2, constitutive curves only.",
        "The plot does not reconstruct the inset microstructures or solve inverse homogenization. "
        "The optimization companion uses Emin=1e-9 for a nonsingular state solve; the curve experiment uses the exact void limit.",
        overrides={"nu": 1/3}),
}

for _name, _label, _spec, _equations, _source, _target, _limits in (
    ("steps", "Equal-step continuation", {"type": "steps", "start": 1., "end": 3., "step": .5, "every": 20},
     [(r"p(k)=\min(p_{\max},p_0+\Delta p\lfloor k/n\rfloor)", "k counts completed iterations; a value is set before the next step.")],
     "https://doi.org/10.1007/BF01214002", "General SIMP continuation; no source figure for this exact clock.",
     "The increment and interval are Toporia demonstration settings, not a reproduced research trajectory."),
    ("geometric", "Geometric beta continuation", {"type": "geometric", "start": 1., "end": 128., "factor": 2., "every": 50},
     [(r"\beta(k)=\min(128,2^{\lfloor k/50\rfloor})", "The paper doubles beta every 50 steps or at convergence; this clock implements the fixed-interval branch.")],
     WANG, "Wang et al. (2011), section 4 continuation accompanying Figures 3-4.",
     "A schedule plot verifies the fixed-interval rule only. It omits early increases at convergence and does not reproduce an optimized paper design."),
    ("linear", "Linear parameter ramp", {"type": "linear", "start": 1., "end": 3., "after": 20, "over": 80},
     [(r"p(k)=p_0+(p_1-p_0)\mathrm{clip}((k-a)/n,0,1)", "Hold, interpolate linearly, and remain at the final value.")],
     "", "Toporia engineering rule; no direct research figure.",
     "This function has no claimed originating paper. A parameter-history demonstration is not a research-figure reproduction."),
    ("settled", "Convergence-triggered beta", {"type": "settled", "start": 1., "end": 128., "factor": 2.,
       "change_below": .03, "settle": 1, "min_every": 10, "max_every": 50},
     [(r"\beta^+=\min(128,2\beta)", "Increase after a sufficiently settled design or the maximum interval; minimum level duration is enforced.")],
     WANG, "Convergence-triggered continuation described in section 4; exact design history unavailable.",
     "The synthetic change signal and minimum-duration guard are declared Toporia choices. "
     "The source paper's actual observed design history is not reconstructed."),
):
    _path = "filters[1].beta" if _name in {"geometric", "settled"} else "interpolation.penal"
    CASES["schedule_" + _name] = _case(_label, "schedule", _name, _spec, _equations,
        "Plot actual schedule values at completed-iteration boundaries. Compare to an independent clock/event simulation.",
        _source, _target, _limits, schedules=[{"path": _path, **_spec}],
        # Beta continuation runs on MMA (move 0.1), the optimiser of Wang et al. (2011): OC at its default
        # move 0.2 lets saturated variables bounce, and members flip once beta reaches 128 (C 210 -> 1260).
        overrides={"max_iter": 450, "method": "q4+mma", "method_params": {"move": .1}}
                  if _name in {"geometric", "settled"} else {})

SYMBOLS = {
    "pde": "x: input cell densities; rho-bar: smoothed field; T: element-to-node averaging; "
           "K_f/M_f: filter stiffness/mass matrices; r: PDE length; rmin: radius in cells; F: discrete filter; "
           "J: scalar response. Zero normal derivative imposes no flux.",
    "pde_anisotropic": "x: source density; rho-bar: smoothed density; D: diagonal diffusion tensor; "
                      "r_a: radius along axis a in cells; A: finite-volume matrix; J: scalar response.",
    "heaviside": "x: input density; P(x): projected density; beta: sharpness; eta: threshold; P prime: derivative with respect to x. All are dimensionless.",
    "heaviside_volume": "x_j: input cell value; eta(x): global threshold; P_x and P_eta: partial derivatives of projection; "
                        "s_j: incoming sensitivity; g_j: input sensitivity. The implicit derivative needs a nonzero sum of P_eta.",
    "morphology": "x: input density; D/E: smooth dilation/erosion; O/C: opening/closing; beta: sharpness; "
                  "H: distance weights; w: normalized weights. Indices i/j refer to output/input cells.",
    "am": "x_i: blueprint density; rho_i: printed density; s_i: support measure; S_i: supporting cells below; "
          "Ns: stencil size; P/Q: support exponents; xi0: normalization density; epsilon=1e-4: smooth-min parameter. "
          "Tiny regularizing shifts/backshifts are retained in the implementation.",
    "symmetry": "x: input field; M: reflection operator; I: identity; P: averaging projection. "
                "Both-axis symmetry composes horizontal and vertical averages.",
    "routing": "x: source density; x-tilde: thresholded closing input; tau: low-density threshold; chi: interior mask; "
               "D/E: normalized p-mean dilation and complementary erosion; "
               "P: sharpness exponent; n_i: valid stencil count; alpha: ramp fraction; m: cells per mm; "
               "r_mm/r_el: tool radius in mm/cells. The boundary band bypasses closing.",
    "extrusion": "P: average-and-broadcast operator; x_kj: input cell density; ny: number of cells along y; "
                 "i/j: output y/x cell index. All output rows share one cross-section.",
    "pattern": "c/d: repetition-cell indices; i: position inside a cell; nc: number of repetitions; "
               "P: folding-average-and-repeat operator. Density is dimensionless.",
    "casting": "x_k: input density along a draw line; rho_k: output; k=0: parting-plane cell; "
               "smin: corrected smooth minimum; epsilon=1e-6. The reverse sweep differentiates all preceding dependencies.",
    "machining": "u: tool-direction velocity; D: diffusion coefficient set by Peclet number; h: mean cell size; "
                 "T_a: shadow from direction a; T_star: combined shadow; p<0: intersection exponent; n: direction count. "
                 "Beta and eta control the final bounded projection.",
    "self_support": "psi: input design; phi: supported field; S_i: lower support wedge; H_T: tanh gate; "
                    "T: support threshold; b: support sharpness; F_cone: local cone average; mu: averaged supported field; "
                    "beta: local projection sharpness; rho: physical density.",
    "ramp": "rho: physical density; E: modulus; E0/Emin: solid/soft moduli; q: rational penalty; E prime: density derivative.",
    "ordered_simp": "rho: normalized density; rho_i: candidate material densities; f_i: candidate modulus fractions; "
                    "t: local interval coordinate; p: penalty; f: interpolated modulus fraction; "
                    "A_i/B_i: original global-power coefficients. This implementation requires increasing density and nondecreasing moduli.",
    "sinh": "rho: physical density; eta1: stiffness measure; eta2: effective resource cost; p: penalty; "
            "eta2 prime: derivative of resource cost. Effective cost differs from true geometric volume except at 0/1.",
    "hashin_shtrikman": "rho: physical density; E/E0/Emin: effective/solid/soft moduli; nu: fixed Poisson ratio; "
                       "q: stricter bulk/shear penalty. The source curve uses normalized E0=1, Emin=0, nu=1/3.",
    "schedule_steps": "k: completed iterations; p0/pmax: starting/final penalty; Delta p: increment; n: steps per level; floor: integer part.",
    "schedule_geometric": "k: completed iterations; beta: projection sharpness. Values double after each 50 completed steps and stop at 128.",
    "schedule_linear": "k: completed iterations; p0/p1: start/end; a: initial hold; n: ramp duration; clip: restrict to [0,1].",
    "schedule_settled": "beta: current projection sharpness; beta-plus: next level. The event uses reported design change, "
                        "a consecutive-settled count, minimum level duration and maximum-duration fallback; all settings are recorded.",
}


def recipe(case_id):
    """Existing numerical parts only; the transfer-figure command is in help."""
    case = CASES[case_id]
    scenario = replace(mbb_beam.scenario(), **({"nu": 1/3} if case_id == "hashin_shtrikman" else {}))
    solver = replace(mbb_beam.solver(), method="q4+oc", max_iter=200,
                     filter_specs=[{"type": "density", "rmin": 2.4}])
    if case["kind"] == "filter":
        specs = [dict(case["spec"])] if case_id in {"pde", "pde_anisotropic"} else [
            {"type": "density", "rmin": 2.4}, dict(case["spec"])]
        solver = replace(solver, filter_specs=specs)
    elif case["kind"] == "interpolation":
        solver = replace(solver, interpolation=dict(case["spec"]))
    elif case["kind"] == "schedule":
        specs = [{"type": "density", "rmin": 2.4}]
        if case_id in {"schedule_geometric", "schedule_settled"}:
            specs.append({"type": "heaviside", "beta": 1., "beta_max": 128.})
        solver = replace(solver, filter_specs=specs, schedules=[dict(spec) for spec in case["schedules"]])
    for name, value in case["overrides"].items():
        if name != "nu":
            solver = replace(solver, **{name: dict(value) if isinstance(value, dict) else value})
    return scenario, solver


def description(case_id):
    case = CASES[case_id]
    scenario, solver = recipe(case_id)
    return ResearchDescription(
        question="What does " + case["label"] + " compute, and which part of its research claim can be reproduced?",
        setup=("QUARANTINED: " + QUARANTINED[case_id] + " " if case_id in QUARANTINED else "") +
              "Figure settings: " + str(case["spec"]) + ". The diagnostic field/curve and all parameters are saved "
              "by the reproduction command. GUI Run is an optimization companion on the half-MBB beam "
              f"(60 by 20 domain; mesh resolution {solver.m}; maximum {solver.max_iter} steps; "
              f"volume budget {scenario.volfrac}); it does not launch the transfer-curve experiment.",
        computes=case["computes"], equations=case["equations"],
        symbols=SYMBOLS[case_id] + " Superscript T denotes transpose where used.",
        source_url=case["source"], figure=case["target"],
        comparison="The report separates independent numerical checks, equation/curve agreement, "
                   "paper-visual comparison and unresolved reproduction. Diagnostic success alone never sets a paper match.",
        limitations=case["limits"],
        reproduce="python -m experiments.research_batch2 --case " + case_id,
        functions=(case["function"],))


def metadata(case_id):
    case = CASES[case_id]
    return ("Research: " + case["label"], "Demonstrate " + case["label"] + "; see preset help for mathematics and evidence scope.",
            "Research demonstration. Papers: " + case["source"] if case["source"] else
            "Toporia engineering demonstration; no originating research figure claimed.", description(case_id))
