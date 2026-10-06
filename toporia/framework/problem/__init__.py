"""framework.problem — WHAT is solved, and how a run is described.

    scenario.py  Scenario: domain, supports, loads, material, volume budget, objective, constraints
    mesh.py      the Scenario meshed at a resolution: elements, node masks, per-element bounds
    solver.py    Solver: method, its parameters, filters, mesh resolution, stopping rule
    run.py       Run = Scenario + Solver + Output, and parameter paths into it
    files.py     Scenario and Solver as JSON files, and their fingerprints
"""
