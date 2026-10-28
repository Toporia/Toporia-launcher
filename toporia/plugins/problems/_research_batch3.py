"""Research recipes for existing updaters, representations and level sets.

No algorithm is defined here. GUI Run is the bounded optimization companion;
the experiment command also makes operator checks and comparison figures.
"""

from copy import deepcopy
from dataclasses import replace

from . import mbb_beam
from ._research import Equation, ResearchDescription


def eq(latex, text):
    return Equation(latex, text)


MMA = (
    eq(r"\widetilde f(z)=r+\sum_j\left(\frac{p_j}{U_j-z_j}+\frac{q_j}{z_j-L_j}\right)",
       "MMA builds a separable convex reciprocal approximation between moving asymptotes; nonnegative coefficients match local derivatives."),
    eq(r"z^+=\arg\min_{\ell\leq z\leq h}\widetilde f_0(z),\quad\widetilde g_i(z)\leq0",
       "A dual/subproblem solve proposes the next bounded design. The local one-budget variant and external multi-constraint implementations are distinct."),
)
AL = eq(r"P(g;\lambda,\mu)=\frac{\max(0,\lambda+\mu g)^2-\lambda^2}{2\mu},\quad\lambda^+=\max(0,\lambda+\mu g)",
        "An inequality penalty acts only when its shifted violation is positive. Its finite-iteration output need not satisfy the constraint.")
UNION = eq(r"\rho=1-\prod_b(1-\rho_b),\quad\nabla_z C=J_\rho(z)^{\mathsf{T}}\nabla_\rho C",
           "Toporia joins components by a bounded product union and carries sensitivities through its Jacobian. This differs from a maximum or p-norm union.")
BAR = eq(r"\phi_b=\frac{t_b}{6}\left[1-(x'_b/L_b)^6-(y'_b/t_b)^6\right],\quad\rho_b=\frac{1+\tanh(\phi_b/\epsilon)}{2}",
         "Rotate and translate into each bar's axes, evaluate its superellipse, then smooth its boundary at element centres.")
BASE_SYMBOLS = ("z: design variables; rho: physical element density; C or f: objective; g: normalized inequality, feasible when <=0; "
                "J: Jacobian; superscript T: transpose; plus: next iterate; ell/h: move-and-box bounds. "
                "K: stiffness; u: displacement; F: applied load; N: cell count. Coordinates use the scenario's mm units; density is dimensionless. ")


def case(function, label, equations, symbols, computes, target, source, limits, **settings):
    return dict(function=function, label=label, equations=equations, symbols=symbols,
                computes=computes, target=target, source=source, limits=limits, settings=settings)


CASES = {}


def updater(name, label, equations, symbols, computes, target, source, limits, **settings):
    CASES[name] = case("updater:" + name, label, equations, symbols, computes, target, source, limits, **settings)


for name, label, source in (
    ("mma", "MMA: local one-budget variant", "https://doi.org/10.1002/nme.1620240207"),
    ("pymoto_mma", "MMA through pyMOTO", "https://github.com/aatmdelissen/pyMOTO"),
    ("pymoto_gcmma", "GCMMA through pyMOTO", "https://doi.org/10.1137/S1052623499362822"),
    ("mmapy_mma", "MMA through mmapy", "https://github.com/arjendeetman/GCMMA-MMA-Python"),
    ("mmapy_gcmma", "GCMMA through mmapy", "https://doi.org/10.1137/S1052623499362822"),
    ("nlopt_mma", "MMA through NLopt", "https://nlopt.readthedocs.io/en/latest/NLopt_Algorithms/"),
):
    updater(name, label, MMA, "L/U: asymptotes; p/q: reciprocal coefficients; r: value offset.",
            "Calls the existing updater through the same Q4 model. Histories record objective evaluations as well as accepted/displayed steps; GCMMA can evaluate multiple trial designs.",
            "Svanberg MMA/GCMMA numerical examples: numbered panel and original problem inputs still to recover.", source,
            "The common MBB diagnostic is not a Svanberg paper figure. Library algorithms, scaling, safeguards and stopping rules differ; matching final compliance alone would not establish algorithm equivalence.")

updater("conlin", "CONLIN mixed variables", (
    eq(r"\widetilde f(z)=f(z^k)+\sum_{g_j\geq0}g_j(z_j-z_j^k)+\sum_{g_j<0}[-g_j(z_j^k)^2](1/z_j-1/z_j^k)",
       "Positive derivatives use direct variables; negative derivatives use reciprocals, giving a separable convex approximation."),
), "g_j: derivative at the current point; k: iteration.",
    "Builds mixed-variable objective/constraint approximations and solves their multiplier dual with L-BFGS-B.",
    "Fleury-Braibant (1986) numerical example: panel/inputs pending.", "https://doi.org/10.1002/nme.1620230307",
    "Own implementation with move limits; no published CONLIN trajectory is used as a reference.")
updater("oc_multi", "OC with several multipliers", (
    eq(r"z_j^+=\mathrm{clip}_{[\ell_j,h_j]}\left[z_j\left(\max(0,-d_j/\sum_i\lambda_i v_{ij})\right)^\eta\right]",
       "Cyclic multiplier searches generalize the multiplicative OC rule; safeguards handle gradient signs."),
), "d: objective direction; v_ij: gradient of constraint i; lambda_i: multiplier; eta: damping exponent.",
    "Uses one volume and one aggregate stress constraint in the companion, so the extra multiplier path is exercised.",
    "Zhou-Rozvany (1991) COC examples: panel/inputs pending.", "https://doi.org/10.1016/0045-7825%2891%2990046-9",
    "Toporia's cyclic-bisection variant does not establish feasibility or convergence of general signed-gradient constraints.")
for name, label in (("beso", "BESO soft kill"), ("beso_hard", "BESO hard kill")):
    updater(name, label, (
        eq(r"V_{k+1}=\max(V_*,(1-ER)V_k),\quad z_j^+\in\{z_{\min},1\}",
           "Reduce the allowed material gradually and rank filtered/history-smoothed sensitivities, with a cap on additions."),
    ), "V: material budget; V*: final budget; ER: evolutionary removal fraction; z_min: soft or hard void bound.",
        "Starts fully solid, evolves a binary design and uses objective-window convergence rather than maximum element change.",
        "Huang-Xie BESO beam examples: exact panel and history pending.", "https://doi.org/10.1016/j.finel.2007.06.006",
        "Hard kill uses exact design void bounds but the physics retains ersatz stiffness. Sensitivity histories, additions and discrete ties matter.")
updater("floating_projection", "Floating projection update", (
    eq(r"P_{\beta,\eta}(x)=\frac{\tanh(\beta\eta)+\tanh(\beta(x-\eta))}{\tanh(\beta\eta)+\tanh(\beta(1-\eta))}",
       "The threshold floats to preserve the trial mass; an outer multiplier targets actual filtered volume. The beta-to-zero limit is identity."),
    eq(r"\sum_jP_{\beta,\eta}(x_j)=\sum_jx_j",
       "A scalar root imposes mass preservation before subsequent bounds and physical-volume checking."),
), "x: OC ratio trial; beta: sharpness; eta: mass-preserving threshold.",
    "Combines a damped ratio step, a floating projection and internal sharpness continuation.",
    "Huang (2020 preprint), FPTO examples: optimization panel/settings pending.", "https://arxiv.org/abs/2006.04306",
    "Own modular filter ordering and shared move limit; not the author's smooth-boundary reconstruction. A capped run may leave internal continuation unfinished.", move=0.02)
updater("simpl", "SiMPL primal and latent steps", (
    eq(r"\psi=\log(\rho/(1-\rho)),\quad\rho^+=\sigma(\psi-\alpha(\widehat d+\lambda\widehat v)),\quad\sigma(s)=1/(1+e^{-s})",
       "A gradient step and volume correction are straight in latent coordinates and curved in densities; lambda can be zero."),
), "psi: latent logit; alpha: adaptive step; d-hat/v-hat: max-norm-normalized objective/volume gradients; lambda: budget multiplier.",
    "Plots a controlled two-variable instance of the primal/latent construction plus a bounded MBB optimization.",
    "Kim et al., arXiv:2411.19421v2, Figure 1 schematic and equations 14-15; own numerical coordinates.", "https://arxiv.org/html/2411.19421v2",
    "Schematic equation check only. The source does not specify these plotted coordinates. Toporia normalizes gradients and changes step adaptation, and does not reproduce the reported SiMPL-A/B histories.")
updater("adam", "Adam moments and volume penalty", (
    AL,
    eq(r"m_t=\beta_1m_{t-1}+(1-\beta_1)d_t,\quad v_t=\beta_2v_{t-1}+(1-\beta_2)d_t^2",
       "First and second moments average the augmented objective direction componentwise."),
    eq(r"z^+=\mathrm{clip}\left(z-a_t\frac{m_t/(1-\beta_1^t)}{\sqrt{v_t/(1-\beta_2^t)}+10^{-8}}\right)",
       "Bias correction removes zero-initialization bias; the configured learning rate decays and box clipping follows."),
), "m/v: moments; beta1/beta2: decay factors; a_t: decayed rate; d_t: normalized augmented gradient; lambda/mu: multiplier/penalty.",
    "Runs a deterministic independent moment recurrence check and the actual volume-penalized Q4 optimizer.",
    "Kingma-Ba Algorithm 1; Figure 1 learning curves require the original data/task and are not this MBB diagnostic.", "https://arxiv.org/abs/1412.6980",
    "Algorithm recurrence agreement is not reproduction of machine-learning figures. Toporia's default beta1=0.5, decaying rate, clipping and volume penalty are topology-specific choices.", lr=0.01)
updater("pto", "PTO sensitivity-proxy variant", (
    eq(r"s_j=\max(0,-\partial C/\partial z_j)^q,\quad z_j^+=\mathrm{clip}\left(z_j+\mathrm{clip}(\gamma(a s_j-z_j),-m,m)\right)",
       "A scalar allocation factor a is bisected on actual volume. This code uses negative sensitivity as its energy proxy."),
), "s: allocation weight; q: exponent; gamma: relaxation; a: allocation factor; m: move limit.",
    "Allocates material in proportion to a filtered sensitivity proxy; demonstrates the existing variant without changing it.",
    "Biyikli-To (2015), Figure 3 MBB PTOc panel (120 by 40, fraction 0.35).", "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0145041",
    "The published PTOc uses element compliance allocation; a negative filtered sensitivity is not proportional to it across varying density. Current q=3/relax=0.2 also differs from the source study. No source replication claimed.")
updater("tobs", "TOBS integer design steps", (
    eq(r"\min_\delta d^{\mathsf{T}}\delta,\quad g_i+J_i\delta\leq0,\quad z+\delta\in\{0,1\}^N",
       "Each sequential MILP chooses binary switches under linearized constraints and a switch-count trust limit."),
), "delta: element switches; d: objective gradient; J_i: constraint derivative.",
    "Solves the existing binary linear subproblems with SciPy HiGHS, then re-evaluates the actual physical design.",
    "Picelli et al. (2021) TOBS101 examples: numbered panel/inputs pending.", "https://doi.org/10.1007/s00158-020-02719-9",
    "Linearized feasibility is not nonlinear feasibility; Toporia's relaxation and trust controls must be aligned with the source.")
updater("augmented_lagrangian", "Local-stress augmented Lagrangian", (AL, *MMA),
    "lambda/mu: one multiplier/penalty per local stress observation; L/U,p/q,r: MMA approximation data.",
    "Runs Q4 compliance with a local relaxed-stress penalty; MMA handles the volume budget while local multipliers update every inner block.",
    "Giraldo-Londono-Paulino PolyStress examples: matching mesh, stress relaxation and numbered panel pending.", "https://doi.org/10.1007/s00158-020-02760-8",
    "Q4 ersatz cells and the current density-relaxed stresses differ from PolyStress polygonal meshes. Inspect the exact stress ratio, not just small motion.")
for name, label, algorithm in (
    ("scipy_slsqp", "SLSQP through SciPy", "SQP"),
    ("nlopt_slsqp", "SLSQP through NLopt", "SQP"),
    ("scipy_trust_constr", "Trust-constr through SciPy", "TRUST"),
    ("nlopt_ccsaq", "CCSAQ through NLopt", "CCSAQ"),
    ("nlopt_auglag", "Augmented Lagrangian through NLopt", "AL"),
    ("nullspace", "Null-space gradient flow", "NULL"),
):
    formula = {
        "SQP": eq(r"\min_s d^{\mathsf{T}}s+\frac{1}{2}s^{\mathsf{T}}Bs,\quad g+Js\leq0",
                  "Sequential quadratic programming models curvature and linearizes constraints before a safeguarded step."),
        "TRUST": eq(r"\min_{\|s\|\leq\Delta}m(s),\quad g(z)+J(z)s\leq0",
                    "A trust region bounds the local model step; the library also uses slack/barrier machinery for inequalities."),
        "CCSAQ": eq(r"\widetilde f_i(s)=f_i+d_i^{\mathsf{T}}s+\frac{1}{2}s^{\mathsf{T}}D_i s",
                    "Conservative separable quadratic models are corrected until they bound trial responses; this is the quadratic relative of MMA."),
        "AL": AL,
        "NULL": eq(r"\dot z=-\alpha_J P_{\ker J_A}\nabla f-\alpha_C J_A^\dagger g_A",
                   "Project objective descent along active-constraint tangents and add a feasibility-restoration direction; bounds are library constraints too."),
    }[algorithm]
    source = ("https://doi.org/10.1051/cocv/2020015" if algorithm == "NULL" else
              "https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html" if name == "scipy_slsqp" else
              "https://docs.scipy.org/doc/scipy/reference/optimize.minimize-trustconstr.html" if algorithm == "TRUST" else
              "https://nlopt.readthedocs.io/en/latest/NLopt_Algorithms/")
    updater(name, label, (formula,),
            "s: proposed step; d: objective gradient; B/D: curvature model; J: constraint Jacobian; Delta: radius; A: active rows; dagger: pseudoinverse; alpha: flow weights; lambda/mu: AL multiplier/penalty.",
            "The adapter supplies exact model derivatives, bounds and normalized constraints to the existing external optimizer. Displayed callbacks and physics evaluations are counted separately.",
            "Original optimizer numerical example: identified figure and complete inputs pending; library documentation reviewed separately.", source,
            "The coarse MBB companion checks adapter execution, not the source optimizer's paper figure or global optimality. Small steps, library success and feasibility are separate observations.")


def representation(name, label, equations, symbols, computes, target, source, limits, **spec):
    identity = "mmc" if name == "mmc_variable" else name
    CASES[name] = case("representation:" + identity, label, equations, symbols, computes, target, source, limits,
                       representation=dict(type=identity, **spec))


representation("mmc", "MMC constant-thickness bars", (BAR, UNION),
               "b: bar index; x'/y': local axes; L/t: half-length/half-thickness; epsilon: physical smoothing width.",
               "Five normalized variables per bar set centre, size and angle. Product-union and element-centre smoothing differentiate back to those variables.",
               "Guo et al., arXiv:1404.4820, Figure 8 component and zero contour; own geometry parameters.",
               "https://arxiv.org/pdf/1404.4820",
               "Zero-contour construction is a controlled instance, not the paper image coordinates or optimized cantilever. Product union/tanh differ from the reference implementation.", n_x=3, n_y=2)
representation("mmc_variable", "MMC variable-thickness bars", (
    eq(r"T(u)=t_2+\frac{1}{2}(t_3-t_1)u+\frac{1}{2}(t_1+t_3-2t_2)u^2,\quad u=x'/L",
       "A parabola interpolates the left, centre and right half-thickness; equal values recover a constant bar."), BAR, UNION,
), "u: local axial coordinate; t1/t2/t3: half-thickness samples; T replaces t in the bar formula; b,L,epsilon as for constant MMC.",
    "Seven normalized variables per bar let its thickness taper or bulge. A thickness floor and product union remain in use.",
    "Zhang et al. (2016) variable-thickness MMC: exact numbered component/optimized panel pending.", "https://doi.org/10.1007/s00158-015-1372-3",
    "Source and code thickness parameter ordering must be aligned before an MMC188 comparison. Tanh/product union and centre sampling are independent choices.", thickness="variable", n_x=3, n_y=2)
representation("mmv", "MMV superelliptical holes", (
    eq(r"\rho=\prod_b(1-H(\phi_b))", "Complement the smooth union: solid remains outside the moving superelliptical holes."), BAR,
), "H: smoothed tanh; b: hole index; x'/y',L/t,epsilon: local superellipse geometry and smoothing width.",
    "Moves a fixed set of five-parameter 2D holes, reusing the MMC Jacobian with complementary signs.",
    "Zhang et al. (2017) 3D MMV: source geometry/panel incompatible with this restricted 2D variant.", "https://doi.org/10.1016/j.cma.2017.05.002",
    "The source uses 3D B-spline void surfaces and DOF removal; this variant cannot reproduce them and cannot nucleate new holes.", n_x=3, n_y=2)
representation("bspline", "B-spline density coefficients", (
    eq(r"\rho=B_y Z B_x^{\mathsf{T}},\quad\nabla_Z C=B_y^{\mathsf{T}}(\nabla_\rho C)B_x",
       "Tensor-product basis evaluation maps the coefficient grid to element centres; the backward map is its transpose."),
    eq(r"B_{ij}\geq0,\quad\sum_jB_{ij}=1", "Partition of unity preserves constants and keeps density inside coefficient bounds."),
), "Z: coefficient grid; Bx/By: clamped uniform spline basis matrices; degree=3; 8 by 4 coefficients.",
    "Evaluates a smooth field with 32 coefficients on the finer FE grid, then sends physical gradients back through the separable transpose.",
    "Qian (2013) B-spline density-space examples: numbered panel and original knots pending.", "https://doi.org/10.1016/j.cma.2013.06.001",
    "A controlled coefficient field and independent basis check do not reproduce an optimized paper topology or its knot refinement study.", n_x=8, n_y=4, degree=3)
representation("geometry_projection", "Geometry projection capsule bars", (
    eq(r"d=R-\mathrm{dist}(x,[a,b]),\quad t=\mathrm{clip}(d/r,-1,1)",
       "Distance to a capsule medial segment defines an inside-positive boundary distance normalized by the sampling window."),
    eq(r"H_2(t)=\frac{1}{2}+\frac{\arcsin(t)+t\sqrt{1-t^2}}{\pi},\quad H_3(t)=\frac{1}{2}+\frac{3}{4}t-\frac{1}{4}t^3",
       "A locally flat interface cuts a disk or ball; these are its area/volume fractions, independently checked by quadrature."), UNION,
), "a/b: segment endpoints; R: fixed capsule radius; r: sampling radius; t: normalized signed distance; H2/H3: 2D/3D cap fractions; alpha: activation multiplying each component.",
    "Projects floating fixed-radius capsule bars with activation variables, then combines them through a bounded product union.",
    "Smith-Norato (2020), Figure 1 geometry and equations 1-3: cap construction; optimized examples not reproduced.", "https://link.springer.com/article/10.1007/s00158-020-02552-0",
    "The cap-integral comparison checks the construction with explicit inside-positive signs. Published HTML equation/sign conventions need care. Fixed radius, product union and separately penalized combined density differ from GPTO.", n_x=3, n_y=2)
representation("neural", "Neural coordinate density", (
    eq(r"h_{k+1}=\tanh(h_k W_k+b_k),\quad\rho=\sigma(h_d W_d+b_d)",
       "A seeded coordinate network represents densities; a sigmoid bounds output and every weight/bias is optimized."),
    eq(r"\nabla_\theta C=J_\rho(\theta)^{\mathsf{T}}\nabla_\rho C",
       "Explicit NumPy reverse propagation multiplies physical sensitivities by the network Jacobian; no training data or surrogate is used."),
), "h0: normalized cell coordinates; h: hidden activations; W/b: weights/biases; d: hidden depth; theta: all weights/biases; sigma: logistic function.",
    "Uses two 20-wide tanh layers and sigmoid output, initialized to uniform fraction, with the existing Adam updater.",
    "Chandrasekhar-Suresh TOuNN (2021): architecture/optimization figure alignment pending.", "https://doi.org/10.1007/s00158-020-02748-4",
    "TOuNN uses batch-normalized LeakyReLU and AMSGrad rather than this tanh/Adam-AL variant. Gray fields, approximate volume and local optima remain possible.", width=20, depth=2, seed=0)

for name, label, equations, symbols, target, source, limits in (
    ("levelset", "RBF level-set evolution", (
        eq(r"\Phi=G a,\quad G\dot a=b", "Dense radial-basis interpolation maps coefficients to the nodal level-set field; an evolution solve updates them."),
    ), "Phi: nodal level-set values, positive solid; G: augmented multiquadric interpolation matrix; a: coefficients including polynomial terms; b: evolution forcing.",
     "Wei et al. (2018) TOPRBF cantilever: numbered panel/settings pending.", "https://doi.org/10.1007/s00158-018-1904-8",
     "Mean instead of median energy normalization, guarded rescaling and clipped field make this a numerical variant. Dense node matrices limit mesh size."),
    ("levelset_hamilton_jacobi", "Hamilton-Jacobi level-set evolution", (
        eq(r"\partial_t\phi=V|\nabla\phi|,\quad T=(4\sigma:\sigma-\mathrm{tr}(\sigma)^2)/E",
           "A positive-inside Godunov step advances boundaries; the circular-hole topological benefit can introduce new voids."),
    ), "phi: signed distance in mm; V: normalized, volume-controlled boundary velocity; T: removed-area-normalized plane-stress topological derivative; sigma: solid stress; E: solid modulus.",
     "Challis (2010) HJ/topological-derivative examples: numbered panel/inputs pending.", "https://doi.org/10.1007/s00158-009-0430-0",
     "Independent positive-inside, physically scaled variant with normalized AL feedback, EDT reinitialization and cell-centre sampling; not the source algorithm trajectory."),
    ("levelset_reaction_diffusion", "Reaction-diffusion level-set evolution", (
        eq(r"(I-\Delta t\,\ell^2\Delta)\phi^+=\phi+\Delta t(T/\langle|T|\rangle-\lambda)",
           "Implicit no-flux diffusion regularizes the cell-centred field; bisection chooses a multiplier on the updated smoothed volume before clipping."),
    ), "phi: dimensionless positive-solid field; Delta t: pseudo-time step; ell: diffusion length in mm; Delta: Laplacian; T: topological benefit; lambda: volume multiplier; brackets: cell average.",
     "Otomori et al. (2015) reaction-diffusion examples: numbered panel/inputs pending.", "https://doi.org/10.1007/s00158-014-1190-z",
     "Cell-centred backward Euler, cubic Heaviside and bisected volume differ from levelset88's augmented-Lagrangian feedback; source plane-stress tensor is not the circular-hole tensor."),
):
    CASES[name] = case("method:" + name, label, equations, symbols,
                       "Evolves its own level-set representation and volume control; does not use a composable updater or the selected representation/filter chain.",
                       target, source, limits)


def recipe(case_id):
    data = CASES[case_id]
    kind, identity = data["function"].split(":")
    scenario = mbb_beam.scenario()
    solver = replace(mbb_beam.solver(), m=0.5, tol=0., max_iter=120,
                     filter_specs=[dict(type="density", rmin=1.5)], method_params={})
    if kind == "updater":
        solver = replace(solver, method="q4+" + identity, method_params=deepcopy(data["settings"]))
        if identity in {"beso", "beso_hard", "tobs"}:
            solver = replace(solver, representation=dict(type="element_density", start="full"))
        if identity == "augmented_lagrangian":
            scenario = replace(scenario, constraints=[dict(type="local_stress", limit=0.5)])
        if identity == "oc_multi":
            scenario = replace(scenario, constraints=[dict(type="stress", limit=0.5)])
        if identity in {"scipy_trust_constr", "nullspace"}:
            solver = replace(solver, m=0.3, max_iter=80)
    elif kind == "representation":
        solver = replace(solver, method="q4+mma", method_params=dict(move=0.02),
                         representation=deepcopy(data["settings"]["representation"]))
        if identity == "neural":
            solver = replace(solver, method="q4+adam", method_params=dict(lr=0.01), max_iter=300)
    else:
        solver = replace(solver, method=identity, m=0.4, max_iter=160, filter_specs=[])
    return scenario, solver


def description(case_id):
    data = CASES[case_id]
    scenario, solver = recipe(case_id)
    return ResearchDescription(
        question="How does " + data["label"] + " turn a design and sensitivities into the next material field?",
        setup=f"GUI Run is a bounded optimization companion, not a claimed paper reproduction. Half-MBB domain 60 by 20 mm, "
              f"mesh {round(60*solver.m)} by {round(20*solver.m)}, fraction {scenario.volfrac}, E0=1, Emin=1e-9, nu=0.3, "
              f"top-left downward unit load, left horizontal symmetry and bottom-right vertical roller. "
              f"Method {solver.method}; cap {solver.max_iter}; tol=0 (cap or optimizer's own stop). "
              f"Representation {solver.representation}; parameters {solver.method_params}; constraints {scenario.constraints}; "
              f"filters {solver.filter_specs}. Full numerical evidence is separate from this recipe.",
        computes=data["computes"], equations=data["equations"], symbols=BASE_SYMBOLS + data["symbols"],
        source_url=data["source"], figure=data["target"],
        comparison="The experiment records initial/final fields, pre-update objective histories, fresh final compliance, actual physical volume and solve counts. "
                   "Independent operator checks and source reviews are reported separately. All unmatched paper figures remain in to-fix.",
        limitations=data["limits"], reproduce="python -m experiments.research_batch3 --case " + case_id + (
            "; native Figure 3 attempt: python -m experiments.research_pto_attempt" if case_id == "pto" else ""),
        functions=(data["function"],))


def metadata(case_id):
    data = CASES[case_id]
    return ("Research: " + data["label"], "Bounded research companion; see help for mathematics, source and limitations.",
            "Research target, not a match claim. Papers: " + data["source"], description(case_id))
