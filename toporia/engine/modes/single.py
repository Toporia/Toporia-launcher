# engine/modes/single.py — one optimisation, the "Run One" mode.
#
# The run itself is engine.loop.run_single_with_store; this mode adds what an
# interactive single run is for: a summary of the meshed problem before it
# starts, and the convergence history (history.png) after it ends.

from toporia.engine.loop import run_single_with_store
from toporia.framework.problem.mesh import RectangularProblem


def run_one(config, on_iteration=None):
    """Run one optimisation to the end.  Returns (ResultStore, final density).

    `on_iteration(density, objectives, iteration)` is called after every step;
    the GUI uses it to redraw the live canvas.  Pass nothing for a headless run.
    """
    scenario = config.scenario
    # Mesh the problem once here, only to report its size.  The engine does not
    # know how a method numbers its degrees of freedom, so it reports nodes and
    # elements rather than DOFs.
    problem = RectangularProblem(scenario, config.solver.m)
    print(f"[setup] Lx={scenario.Lx} Ly={scenario.Ly} nelx={problem.nelx} nely={problem.nely}")
    print(f"[setup] volfrac={scenario.volfrac} edge_c={len(scenario.edge_constraints)} "
          f"pt_c={len(scenario.point_constraints)} pt_l={len(scenario.point_loads)}")
    n_fixed = int((problem.fixed_nodes | problem.fixed_x_nodes | problem.fixed_y_nodes).sum())
    n_loaded = int(sum(mask.sum() for mask in problem.load_node_sets))
    print(f"[setup] fixed_nodes={n_fixed} loaded_nodes={n_loaded} load_cases={len(scenario.load_cases)}")
    print(f"[setup] passive_elems={int(problem.passive_elements.sum())} "
          f"void_elems={int(problem.void_elements.sum())}")

    store, density = run_single_with_store(config, on_iteration)
    store.save_history()
    return store, density
