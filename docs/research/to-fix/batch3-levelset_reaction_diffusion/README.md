# Reaction-diffusion level-set evolution: unresolved paper comparison

Target: Otomori et al. (2015) reaction-diffusion examples: numbered panel/inputs pending.

Difference/gap: Cell-centred backward Euler, cubic Heaviside and bisected volume differ from levelset88's augmented-Lagrangian feedback; source plane-stress tensor is not the circular-hole tensor.

Recorded execution: 160 steps; iteration limit (160). Fresh final compliance 230.29468; physical fraction 0.5; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Recover a levelset88 panel and align nodal discretization, Heaviside, reaction/diffusion scaling and original AL volume feedback rather than the current bisection.

[Figure](../../evidence/batch3/levelset_reaction_diffusion/figure.png) · [Numerical report](../../evidence/batch3/levelset_reaction_diffusion/report.json) · [Description and math](../../evidence/batch3/levelset_reaction_diffusion/description.html)
