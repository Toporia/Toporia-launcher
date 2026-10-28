# stress_volume: source comparison and remaining work

Functions: response:volume, response:stress

Target: Le et al. stress-constrained design: exact numbered example pending.

Status: paper_reproduction_to_fix. Independent checks passed within their reported scope.

Limits: Own MBB loading and relaxed stresses differ from the source benchmark. Minimum volume under a stress limit can collapse: with MMA move 0.2, or with a loose limit (6 here), one step thins a member, the stress explodes and the design vanishes. Inspect the reported peak and feasibility.

Next: Recover a feasible named source stress design; distinguish summed volume objective from the budget and hold adaptive stress scaling fixed during gradient checks.

[Figure](../../evidence/batch4/stress_volume/figure.png) · [Report](../../evidence/batch4/stress_volume/report.json) · [Math](../../evidence/batch4/stress_volume/description.html)
