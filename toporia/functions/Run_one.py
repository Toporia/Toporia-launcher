# Run_one.py — single optimisation run
#
# Two ways to use this file:
#   1. Run directly from the terminal:  python Run_one.py
#      → uses the config in main(), shows a static matplotlib plot at the end.
#   2. Import run_one() from another module (e.g. the GUI):
#      → caller passes its own config and an optional per-iteration callback.


import time
from dataclasses import replace
import matplotlib.pyplot as plt

from toporia.core.config import LoadCase, TopOptConfig
from toporia.methods import make_method      # factory: returns the chosen algorithm object
from toporia.core.problem import RectangularProblem as BracketProblem   # builds the FEA mesh from the config
from toporia.core.results import ResultStore      # handles saving density PNGs and history


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
    print(f"[setup] fixed_dofs={len(problem.fixed_dofs)} free_dofs={len(problem.free_dofs)}")
    fmax = float(abs(problem.force).max()); fdof = int(abs(problem.force).argmax())
    print(f"[setup] force max={fmax:.4g} at DOF {fdof}  (in free_dofs: {fdof in problem.free_dofs})")
    method = make_method(config.method)
    method.initialize(problem, config)

    store = ResultStore(config.output_dir)  # will save PNGs and convergence data
    obj0, t_cum = None, 0.0                 # baseline objective and cumulative time

    while not method.has_converged():
        t0 = time.perf_counter()            # wall-clock time before this step
        method.step()                       # one iteration of the optimiser
        d   = method.get_density()          # 2-D array: material density per element
        it  = method.get_iteration()        # current iteration number (starts at 1)
        obj = method.get_objective()        # current compliance (lower = stiffer)
        t_cum += time.perf_counter() - t0

        if obj0 is None:
            obj0 = obj                      # remember the first-iteration baseline

        store.record(iteration=it, objective=obj, volume=float(d.mean()),
                     density=d, save_every=config.save_every)

        # Print progress: Δobj shows improvement relative to iteration 1,
        # vol is the current material fraction, t is per-step wall time.
        print(f"it={it:03d} obj={obj-obj0:+.4e} vol={d.mean():.3f}"
              f" t={time.perf_counter()-t0:.2f}s cum={t_cum:.1f}s")

        # Fire the GUI callback if one was provided — this is what updates
        # the live canvas.  If called standalone there is no callback (None).
        if on_iteration:
            on_iteration(d, store.objectives, it)

    store.save_final(method.get_density())  # write final_density.png + history.png
    return store, method.get_density()


def main():
    # ── Edit this config to change what the standalone script runs ────────────
    from toporia.problems import get_default_config
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
