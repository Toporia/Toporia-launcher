# Run_one.py — single optimisation run
#
# Two ways to use this file:
#   1. Run directly from the terminal:  python Run_one.py
#      → uses the config in main(), shows a static matplotlib plot at the end.
#   2. Import run_one() from another module (e.g. the GUI):
#      → caller passes its own config and an optional per-iteration callback.


from dataclasses import replace

import matplotlib.pyplot as plt

from toporia.core.config import LoadCase
from toporia.core.problem import RectangularProblem as BracketProblem  # builds the FEA mesh from the config
from toporia.engine.runner import run_single_with_store


def run_one(config, on_iteration=None):
    """Run a single topology optimisation to convergence.

    Parameters
    ----------
    config       : TopOptConfig  — all settings (mesh, material, solver params)
    on_iteration : callable, optional
        Called after every solver step as on_iteration(density, objectives, iteration).
        Used by the GUI to update the live canvas.  Pass nothing for a headless run.

    Returns
    -------
    (ResultStore, final_density_array)
    """
    # Instantiate the chosen algorithm ("density" or "levelset") and hand it
    # the problem geometry so it can set up its internal data structures.
    problem = BracketProblem(config)
    print(f"[setup] Lx={config.Lx} Ly={config.Ly} nelx={problem.nelx} nely={problem.nely}")
    print(f"[setup] volfrac={config.volfrac} edge_c={len(config.edge_constraints)} "
          f"pt_c={len(config.point_constraints)} pt_l={len(config.point_loads)}")
    # Geometry-level diagnostics only.  The engine deliberately does not know how
    # a method numbers its degrees of freedom, so it reports node and element
    # counts rather than DOF indices.
    n_fixed = int((problem.fixed_nodes | problem.fixed_x_nodes | problem.fixed_y_nodes).sum())
    n_loaded = int(sum(m.sum() for m in problem.load_node_sets))
    print(f"[setup] fixed_nodes={n_fixed} loaded_nodes={n_loaded} "
          f"load_cases={len(config.load_cases)}")
    print(f"[setup] passive_elems={int(problem.passive_elements.sum())} "
          f"void_elems={int(problem.void_elements.sum())}")
    # The loop itself lives in engine/runner.py so there is exactly one place
    # where the stopping rule and the recording are defined.
    store, density = run_single_with_store(config, on_iteration)
    store.save_history()   # run_one is the interactive mode: plot convergence too
    return store, density



def main():
    # ── Edit this config to change what the standalone script runs ────────────
    from toporia.library.problems import get_default_config
    config = replace(
        get_default_config(),
        method="density", m=1, volfrac=0.2,
        filter_specs=[{"type": "density"}], max_iter=50, save_every=10,
        load_cases=[LoadCase(Fmag=1.0, Fa=135, weight=0.5)],
    )
    # Run without a GUI callback — progress is printed to the terminal only.
    store, density = run_one(config)

    # Show a two-panel matplotlib window when done: density field + convergence.
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    axes[0].imshow(1 - density, cmap="gray", origin="lower")  # invert: solid=dark
    axes[0].set_title(f"Final — {config.method}"); axes[0].axis("off")
    rel = [o - store.objectives[0] for o in store.objectives]  # relative compliance
    axes[1].plot(rel)
    axes[1].set(title="Objective", xlabel="Iteration", ylabel="ΔCompliance")
    fig.tight_layout()
    plt.show(block=True)   # block=True keeps the window open until manually closed


if __name__ == "__main__":
    main()
