"""Existing physics/response recipes and grouped post-processing explanations.

Post-processing figures reuse a saved field; GUI Run is an ordinary companion.
No numerical algorithm or executable graph is defined by this module.
"""

from dataclasses import replace

from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Scenario, Solver

from . import column_buckling, force_inverter, heat_sink, mbb_beam, nonlinear_cantilever, vibrating_beam
from ._research import Equation, ResearchDescription

CASES = {}


def add(name, label, functions, equations, symbols, computes, source, target, limits):
    CASES[name] = dict(label=label, functions=tuple(functions.split()), equations=tuple(Equation(*e) for e in equations),
                       symbols=symbols, computes=computes, source=source, target=target, limits=limits)


ELASTIC = (r"K(\rho)u=F,\quad C=F^{\mathsf{T}}u,\quad E(\rho)=E_{\min}+(E_0-E_{\min})\rho^3",
           "Density controls elastic stiffness; the equilibrium solve determines compliance. Physical-volume filtering is differentiated before the update.")
HEAT = (r"K_k(\rho)T=q,\quad C_T=q^{\mathsf{T}}T,\quad\partial_{\rho_e}C_T=-T_e^{\mathsf{T}}(\partial_{\rho_e}K_k)T_e",
        "A steady conduction solve maps prescribed heat input to temperature; a self-adjoint derivative measures the effect of local conductivity.")
EIGEN = (r"K\phi_i=\lambda_i M\phi_i,\quad\omega_i=\sqrt{\lambda_i},\quad\phi_i^{\mathsf{T}}M\phi_i=1",
         "Generalized eigenvalues give squared angular frequencies; mass normalization fixes the scale of their sensitivities.")
ADJOINT = (r"\partial_{\rho_e}\lambda_i=\phi_i^{\mathsf{T}}(\partial_{\rho_e}K-\lambda_i\partial_{\rho_e}M)\phi_i",
           "Differentiate both stiffness and mass for a simple eigenvalue. Aggregation helps crossings but does not make repeated-eigenvector derivatives unique.")

add("solid3d", "3D H8 elasticity", "model:h8 physics:h8_solid", [ELASTIC],
    "K: 3D stiffness; u/F: nodal displacement/force; E: modulus; rho: physical density; C: compliance.",
    "Integrates trilinear eight-node bricks and assembles sparse 3D elasticity; a separate small native-top3d scalar comparison is explicitly distinguished from the GUI line-load convention.",
    "https://www.top3d.app/", "Liu-Tovar top3d reference; small 12x4x2 author-code benchmark, not an identified paper panel.",
    "The GUI companion uses production trapezoidal depth-load quadrature. The native scalar probe explicitly substitutes uniform nodal depth shares. No native final-field or paper-image equality is claimed.")
add("heat2d", "2D heat conduction and thermal compliance", "model:q4_heat physics:q4_heat response:thermal_compliance", [HEAT],
    "K_k: conductivity matrix; T: nodal temperature; q: integrated heat generation/point heat input; C_T: thermal compliance.",
    "Uses Q4 conduction with distributed generation and prescribed-temperature sinks. A separate strip has an analytic quadratic temperature profile.",
    "https://doi.org/10.1007/s00158-005-0584-3", "Gersborg-Hansen et al. heat-conduction examples: exact numbered panel/settings pending.",
    "This is a finite-element variant of a finite-volume source paper. The strip is an independent analytic check; the own half-disc-sink example is not a paper figure.")
add("heat3d", "3D H8 heat conduction", "model:h8_heat physics:h8_heat", [HEAT],
    "K_k/T/q: 3D conductivity, temperature and heat input; C_T: thermal compliance.",
    "Extends conduction to H8 bricks; a depth-uniform strip verifies physical scaling and integrated source loading.",
    "https://doi.org/10.1007/s00158-005-0584-3", "3D extension of steady conduction; no originating 3D source figure selected.",
    "The cited source does not by itself establish this 3D H8 example. 3D extension and analytic verification are distinct from paper reproduction.")
for name, label, functions, equation, source in (
    ("elastic_pymoto", "Elasticity through pyMOTO", "model:pymoto_elastic", ELASTIC, "https://github.com/aatmdelissen/pyMOTO"),
    ("heat_pymoto", "Heat conduction through pyMOTO", "model:pymoto_heat", HEAT, "https://github.com/aatmdelissen/pyMOTO"),
    ("dynamic_pymoto", "Vibration through pyMOTO", "model:pymoto_dynamic", EIGEN, "https://github.com/aatmdelissen/pyMOTO"),
):
    add(name, label, functions, [equation], "K/M: stiffness/mass (or conductivity); F/q: applied force/heat; u/T: response; lambda/omega/phi: eigenvalue/frequency/mode.",
        "Runs the existing optional-library module network. A fixed-design value/gradient comparison uses Toporia's independent native assembly on the same discrete setup.", source,
        "Author-library cross-check; original research figure not identified.",
        "Agreement between two implementations is not agreement with a published optimized design. Internal pyMOTO filters/mass conventions must be aligned explicitly.")
add("dynamic", "Natural frequencies and mode aggregation", "model:q4_dynamic physics:q4_dynamic response:eigenfrequency", [EIGEN, ADJOINT,
    (r"\bar\lambda=(\sum_i\lambda_i^{-p})^{-1/p},\quad J=-\bar\lambda/\bar\lambda_0", "A lower soft minimum is normalized by its first evaluated value and negated for maximization; the objective is not frequency in hertz.")],
    "M: consistent or lumped mass; phi: mass-normalized mode; lambda=omega squared; omega: angular frequency; p: aggregation exponent.",
    "Uses density-dependent stiffness/mass, low-density mass suppression and an attached payload. A separate solid cantilever checks Euler-Bernoulli bending frequencies.",
    "https://doi.org/10.1007/s00158-007-0101-y", "Du-Olhoff beam family: numbered panel and complete payload/mesh inputs pending.",
    "This bounded example uses own coarse settings. Continuum beam theory is an independent slender-beam check; low-density mass interpolation and repeated modes affect source matching.")
add("harmonic", "Undamped harmonic dynamic compliance", "response:dynamic_compliance", [
    (r"(K-\omega^2M)u_\omega=F,\quad C_\omega=|F^{\mathsf{T}}u_\omega|", "The response is an absolute harmonic load-work amplitude; without damping it is singular at a coupled resonance."),
    (r"\partial_\rho C_\omega=-\mathrm{sign}(F^{\mathsf{T}}u_\omega)u_\omega^{\mathsf{T}}(\partial_\rho K-\omega^2\partial_\rho M)u_\omega", "A self-adjoint contraction differentiates the dynamic stiffness away from poles and the absolute-value kink.")],
    "omega: driving angular frequency; K/M/F/u: stiffness, mass, load and displacement amplitude.",
    "Samples a fixed-design frequency-response curve away from the first resonance and runs a bounded low-frequency companion.",
    "https://doi.org/10.1007/BF00370133", "Ma-Kikuchi-Hagiwara (1993) frequency-response family: exact objective, numbered panel and loading pending; PolyDyna is a related transient method.",
    "Own real undamped amplitude response with SIMP/MMA, not the source's homogenization/MOC scheme or PolyDyna's HHT-alpha transient formulation. F-transpose-u is an amplitude quantity, not net work over a cycle. No resonance-crossing optimization or robust band objective is implemented here.")
add("frequency_limit", "Minimum eigenvalue constraint", "response:eigenfrequency_limit", [EIGEN,
    (r"g=1-\bar\lambda/\lambda_*\leq0", "The limit is a squared angular frequency, not a frequency or hertz value; the aggregate is conservative for the first eigenvalue.")],
    "lambda*: minimum allowed eigenvalue; bar-lambda: soft minimum; g: normalized inequality.",
    "The existing multi-constraint optimizer minimizes compliance while imposing a separate eigenvalue limit and volume budget.",
    "https://doi.org/10.1007/s00158-007-0101-y", "Eigenvalue-constrained source design: exact numbered example not recovered.",
    "A bounded companion is not a feasibility guarantee. It does not add new objective or constraint semantics to the framework.")
add("buckling", "Linearized buckling factors", "model:q4_buckling physics:q4_buckling response:buckling_load", [
    (r"Ku=F,\quad(K+\lambda K_\sigma(u,\rho))\phi=0", "Pre-buckling stress supplies geometric stiffness; positive critical load factors are generalized eigenvalues."),
    (r"J=\lambda_*\left(\sum_i\lambda_i^{-p}\right)^{1/p}-1", "Minimizing the inverse-factor norm raises the lowest buckling factors; lambda-star sets the scale and sensitivities include a pre-stress adjoint.")],
    "K_sigma: geometric stiffness; lambda: load multiplier; phi: buckling mode; p: inverse-power aggregation.",
    "Runs the existing Q4 pre-stress and eigenvalue engine, with a separate slender-column Euler check.",
    "https://doi.org/10.1007/s00158-021-02854-x", "Ferrari-Sigmund-Guest column examples: exact paper panel and source settings pending.",
    "Toporia uses an inverse-factor p-norm rather than the source's KS aggregation, plus own column geometry/interpolation. It is not a direct topBuck250 port. Linear buckling omits postbuckling and imperfections.")
add("nonlinear", "Large-displacement elasticity and end compliance", "model:q4_nonlinear physics:q4_nonlinear response:end_compliance", [
    (r"R(u,\rho)=f_{\rm int}(u,\rho)-F=0,\quad K_T\Delta u=-R", "Load increments and Newton steps solve geometrically nonlinear equilibrium using the consistent tangent."),
    (r"J=F^{\mathsf{T}}u,\quad K_T^{\mathsf{T}}a=F,\quad\partial_\rho J=-a^{\mathsf{T}}\partial_\rho R", "The end-load objective uses a tangent adjoint; it is not automatically twice the nonlinear strain energy.")],
    "R: force residual; K_T: tangent stiffness; a: adjoint; F/u: external force and end displacement.",
    "Uses the current total-Lagrangian, load-stepped material/void blend. A fixed uniform field compares the small-load limit with linear elasticity.",
    "https://doi.org/10.1016/j.cma.2014.03.021", "Wang et al./Buhl et al. nonlinear designs: matching source geometry, law and panel pending.",
    "The current void blend, material law, load pad and Newton controls are declared variant choices. A failed Newton solve must remain a failure, not an optimization result.")
add("mechanism", "Compliant force inverter and port adjoint", "model:q4_mechanism physics:q4_mechanism response:output_displacement", [
    (r"(K(\rho)+K_s)u=F,\quad J=-l^{\mathsf{T}}u", "Ground springs represent input/output ports; minimizing the signed negative output maximizes motion in the requested direction."),
    (r"(K+K_s)^{\mathsf{T}}a=-l,\quad\partial_\rho J=-a^{\mathsf{T}}(\partial_\rho K)u", "The signed port objective requires a separate adjoint, unlike self-adjoint compliance.")],
    "K_s: density-independent port springs; l: output-direction selector; a: adjoint.",
    "Optimizes the existing own force inverter. A separate fixed-density reciprocity check swaps input and output load vectors in the same spring-stiffness system.",
    "https://doi.org/10.1080/08905459708945415", "Sigmund force-inverter family: exact paper panel/spring constants not aligned.",
    "Own dimensions, loads and springs are not source replication. Point hinges and disconnected thresholded designs remain possible.")
add("multires", "Multiresolution Galerkin stiffness", "model:q4_multiresolution physics:q4_multiresolution", [
    (r"K_c=P^{\mathsf{T}}K_fP,\quad C_c=F_c^{\mathsf{T}}K_c^{-1}F_c", "Fine material cells contribute subcell-integrated stiffness to a coarse displacement space."),
    (r"K_c u_c=F_c,\quad u_f=P u_c", "A restricted displacement space can overestimate stiffness; an independent fine-Q4 solve is essential.")],
    "P: coarse-to-fine interpolation; Kc/Kf: coarse/fine stiffness; u/F: displacement/load.",
    "Uses the existing aligned subcell integration; compares its final physical density against an independent fine-Q4 evaluation with the same supports and loads.",
    "https://doi.org/10.1007/s00158-009-0443-8", "Nguyen et al. MTOP examples: exact source panel and design/analysis grids pending.",
    "This exact-subcell Galerkin variant differs from the source centroid rule. Fine features can be artificially stiff on the coarse analysis grid.")
add("stress_volume", "Minimum volume with aggregate stress", "response:volume response:stress", [
    (r"J=\sum_e\rho_e,\quad g=\frac{s(\sum_e(\rho_e^q\sigma_{{\rm vm},e})^p)^{1/p}}{\sigma_*}-1", "Minimize summed physical material subject to the existing adaptively scaled p-norm relaxed-stress limit."),
    (r"\max_e(\rho_e^q\sigma_{{\rm vm},e})/\sigma_*-1\leq0", "The exact relaxed peak is recorded separately from the adaptive aggregate; density relaxation is not a full-solid stress certificate.")],
    "sigma_vm: element von Mises stress; sigma*: limit; q: relaxation; p: p-norm exponent; s: adaptive scale; N: cell count.",
    "Exercises the existing minimum-volume objective, separate from the built-in volume budget, with the stress response and an existing multi-constraint updater.",
    "https://doi.org/10.1007/s00158-009-0440-y", "Le et al. stress-constrained design: exact numbered example pending.",
    "Own coarse MBB loading and relaxed stresses differ from the source benchmark. The reported peak/feasibility must be inspected even when motion is small.")
add("local_stress", "Local stress penalties and multiplier fields", "response:local_stress", [
    (r"g_e=\rho_e^q\sigma_{{\rm vm},e}/\sigma_*-1-\epsilon(1-\rho_e)", "Density relaxation and optional void slack define each local inequality."),
    (r"P=\sum_e\frac{\max(0,\lambda_e+\mu g_e)^2-\lambda_e^2}{2\mu}", "The response returns an augmented-Lagrangian penalty, not an ordinary normalized inequality; the matching updater owns multiplier updates.")],
    "lambda_e: local multipliers; mu: penalty; epsilon: void slack; q: stress relaxation; sigma*: limit.",
    "Visualizes the existing relaxed-stress field and penalty diagnostics with the dedicated AL updater.",
    "https://doi.org/10.1007/s00158-020-02760-8", "PolyStress local-stress example: source polygonal mesh/relaxation/panel pending.",
    "The Q4 density-relaxed variant is not a PolyStress port. Finite penalties and a bounded solve do not certify local feasibility.")
add("minimum_length", "Geometric solid and void length indicators", "response:minimum_length", [
    (r"b=H\rho,\quad I_s=\rho e^{-c|Gb|^2}(1-b)^2,\quad I_v=(1-\rho)e^{-c|Gb|^2}b^2", "A physical cone average and discrete gradient identify small solid/void medial features."),
    (r"\max_j a_j\leq {\rm KS}(a)\leq\max_j a_j+1/s", "The normalized nodal KS measure is conservative within its configured aggregation gap; it uses a mesh-dependent one-dimensional tolerance calibration.")],
    "H: cone average; G: discrete gradient in minimum-cell-spacing units; c: radius-based scale; a: normalized nodal violations; s: KS sharpness.",
    "Runs the existing cell-centred geometric constraints and tests straight bars against their calibrated nodal indicator.",
    "https://doi.org/10.1016/j.cma.2015.05.003", "Zhou/Dunning length constraints: exact source panel and projection conventions pending.",
    "Own physical-field/KS variant is not the original three-field formulation. Gray fields, boundary stencils and mesh resolution prevent a universal minimum-feature certificate.")
add("phase_field", "Diffuse-interface energy and compliance", "response:phase_field", [
    (r"J=C/C_{\rm ref}+w\left\langle\frac{\epsilon}{2}|\nabla\rho|^2+\frac{\rho^2(1-\rho)^2}{\epsilon}\right\rangle", "The existing response adds domain-mean Modica-Mortola energy to normalized compliance; w controls the tradeoff."),
    (r"\rho(x)=\frac{1}{1+e^{-\sqrt{2}x/\epsilon}},\quad\gamma=\int_0^1\sqrt{2r^2(1-r)^2}\,dr=\frac{\sqrt{2}}{6}", "A resolved planar transition gives an independent interface-energy limit for this double-well convention.")],
    "epsilon: physical interface scale; w: regularization weight; angle brackets: cell mean; C_ref: full-material reference compliance; gamma: energy per unit interface.",
    "Plots a resolved interface and an ordinary regularized-compliance companion using the existing finite-volume gradient energy.",
    "https://doi.org/10.1016/j.jcp.2009.12.017", "Takezawa et al. Section 2.3 energy family; full numbered source design not reproduced.",
    "This is a fixed-load, symmetric double-well response with Toporia optimizers, not a pressure-load or tilted-well Allen-Cahn port.")

POSTS = {
    "threshold": (r"b_e\in\{0,1\},\quad\sum_e b_e=\mathrm{round}(\sum_e\rho_e)", "Select the densest free cells, preserving pinned regions; ties and integer rounding can change the effective cutting level."),
    "connectivity": (r"G=(V,E),\quad (i,j)\in E\ \Longleftrightarrow\ i,j\ \mathrm{share\ a\ face}", "Connected-component traversal identifies material not touching supports; corner contact alone is not a connection."),
    "feature_size": (r"d(x)=\min_{y\in\mathrm{opposite\ phase}}\|x-y\|", "A sampled distance transform and medial measurements estimate feature widths; they are not continuum guarantees."),
    "grey_level": (r"M_{\rm nd}=\frac{400}{N}\sum_e\rho_e(1-\rho_e)\ \%", "The percent non-discreteness is zero for binary designs and 100 for uniform half-density."),
    "export_svg": (r"\Gamma=\{x:\rho(x)=\eta\}", "Marching contours or explicit geometry produce a physical-coordinate SVG outline; source and orientation are declared."),
    "export_dxf": (r"\Gamma=\bigcup_k\{v_{k,0},\ldots,v_{k,n},v_{k,0}\}", "Closed polylines encode physical millimetres for CAD; an outline is not a structural reanalysis."),
    "smooth_outline": (r"Q_i=\frac{3}{4}P_i+\frac{1}{4}P_{i+1},\quad R_i=\frac{1}{4}P_i+\frac{3}{4}P_{i+1}", "The optional Chaikin rule cuts polygon corners; the default spline is a different smoothing option. Neither preserves structural performance automatically."),
    "export_stl": (r"V_{\rm voxels}=N_s\Delta x\Delta y\Delta z", "Exposed voxel faces become oriented triangles in a binary STL; internal faces are removed and physical spacing sets its volume."),
}
for name, label, names in (("post2d", "Saved-field 2D post-processing", tuple(k for k in POSTS if k != "export_stl")),
                            ("post3d", "Saved-field STL solid export", ("export_stl",))):
    add(name, label, " ".join("postprocessor:"+n for n in names), [POSTS[n] for n in names],
        "rho: saved physical field; b: binary mask; N/Ns: total/solid cell count; eta: contour level; P/Q/R/v: outline points; Delta x/y/z: cell spacing.",
        "The experiment reuses one saved field and applies each existing post-processor, retaining its files/metrics and separate figures. GUI Run executes the ordinary companion; choose the named operations in the existing Post-processing panel or use the experiment command.",
        "", "Own engineering exports/checks and source-inspired metrics; no single originating research figure for the group.",
        "Connectivity/feature estimates, smoothing and exported geometry are separate from physical feasibility. File validity does not establish CAD manufacturability or a paper match.")


def recipe(name):
    if name in {"heat2d", "heat_pymoto"}:
        scenario, solver = heat_sink.scenario(), replace(heat_sink.solver(), m=.2)
        if name == "heat_pymoto":
            solver = replace(solver, method="pymoto_heat+pymoto_mma", filter_specs=[])
    elif name == "heat3d":
        scenario = Scenario(Lx=8., Ly=4., Lz=2., edge_constraints=[EdgeConstraint("left")],
                            load_cases=[LoadCase(Fmag=0.)], objective=dict(type="thermal_compliance"), volfrac=.5, Emin=1e-3)
        solver = Solver(method="h8_heat+oc", m=1., filter_specs=[dict(type="density", rmin=1.5)])
    elif name in {"dynamic", "dynamic_pymoto", "frequency_limit", "harmonic"}:
        scenario, solver = vibrating_beam.scenario(), replace(vibrating_beam.solver(), m=4.)
        if name == "dynamic_pymoto":
            solver = replace(solver, method="pymoto_dynamic+pymoto_mma", filter_specs=[])
        if name == "frequency_limit":
            scenario = replace(scenario, objective=dict(type="compliance"), constraints=[dict(type="eigenfrequency_limit", limit=1e-4)])
            solver = replace(solver, method="q4_dynamic+pymoto_mma")
        if name == "harmonic":
            scenario = replace(scenario, objective=dict(type="dynamic_compliance", omega=.001))
    elif name == "buckling":
        scenario, solver = column_buckling.scenario(), column_buckling.solver()
        scenario = replace(scenario, objective=dict(type="buckling_load"), constraints=[])
        solver = replace(solver, m=.3, method="q4_buckling+mma", schedules=[], filter_specs=[dict(type="density", rmin=1.5)])
    elif name == "nonlinear":
        scenario, solver = nonlinear_cantilever.scenario(), replace(nonlinear_cantilever.solver(), m=.2, method_params=dict(steps=10))
    elif name == "mechanism":
        scenario, solver = force_inverter.scenario(), replace(force_inverter.solver(), m=.4)
    else:
        scenario, solver = mbb_beam.scenario(), replace(mbb_beam.solver(), m=.4, method="q4+mma")
        if name in {"solid3d", "post3d"}:
            scenario = Scenario(Lx=12., Ly=4., Lz=2., volfrac=.3, edge_constraints=[EdgeConstraint("left", "both")],
                                point_loads=[PointLoad(12., 0.)], load_cases=[LoadCase(Fmag=3., Fa=270.)])
            solver = replace(solver, method="h8+oc", m=1.)
        elif name == "elastic_pymoto":
            solver = replace(solver, method="pymoto_elastic+pymoto_mma", filter_specs=[])
        elif name == "multires":
            solver = replace(solver, method="q4_multiresolution+mma", method_params=dict(coarsening=2))
        elif name == "stress_volume":
            scenario = replace(scenario, objective=dict(type="volume"), volfrac=.8, constraints=[dict(type="stress", limit=3.)])
            solver = replace(solver, method="q4+pymoto_mma")
        elif name == "local_stress":
            scenario = replace(scenario, constraints=[dict(type="local_stress", limit=3.)])
            solver = replace(solver, method="q4+augmented_lagrangian")
        elif name == "minimum_length":
            scenario = replace(scenario, constraints=[dict(type="minimum_length", phase="solid", min_length=16.),
                                                      dict(type="minimum_length", phase="void", min_length=16.)])
            solver = replace(solver, method="q4+pymoto_mma")
        elif name == "phase_field":
            scenario = replace(scenario, objective=dict(type="phase_field", interface_width=2.5, perimeter_weight=5.))
            solver = replace(solver, filter_specs=[])
    if name == "post2d":
        solver = replace(solver, m=.5)
    return scenario, replace(solver, max_iter=20 if name == "nonlinear" else 60, tol=0.)


def description(name):
    data = CASES[name]
    scenario, solver = recipe(name)
    return ResearchDescription(
        question="What does " + data["label"] + " compute, and what evidence supports its current implementation?",
        setup=f"GUI Run is a bounded companion, not an assertion of paper reproduction. Domain {scenario.Lx} by {scenario.Ly} by {scenario.Lz}; "
              f"mesh resolution {solver.m}; volume budget {scenario.volfrac}; method {solver.method}; cap {solver.max_iter}; tol=0. "
              f"Objective {scenario.objective}; constraints {scenario.constraints}; parameters {solver.method_params}; filters {solver.filter_specs}. "
              "The saved report records the complete scenario, resolved defaults, physical field and fresh metrics.",
        computes=data["computes"], equations=data["equations"], symbols=data["symbols"], source_url=data["source"],
        figure=data["target"], comparison="Independent analytic, assembly, gradient and file/metric checks are separate from source-figure reproduction. "
        "Histories, fresh final responses and feasibility are recorded without treating a bounded run as convergence.",
        limitations=data["limits"], reproduce="python -m experiments.research_batch4 --case " + name, functions=data["functions"])


def metadata(name):
    data = CASES[name]
    return "Research: " + data["label"], "Existing-function demonstration; see help for mathematics and evidence scope.", (
        "Research target. Papers: " + data["source"] if data["source"] else "Own engineering demonstration; no paper match claimed."), description(name)
