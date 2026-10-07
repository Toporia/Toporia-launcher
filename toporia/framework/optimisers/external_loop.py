# framework/optimisers/external_loop.py — optimisers that insist on running their own loop.
#
# SciPy, NLopt, IPOPT and most optimisers from the literature are written as
# "give me f, g and their gradients, I will call you until I am done".  The
# engine wants the opposite: it owns the loop, so it can draw every design,
# apply the same stopping rule to every method, and stop on request.
#
# ExternalOptimizer reconciles the two.  The library runs in a background
# thread on the flat view (framework/optimisers/flat_view.py).  Whenever it reaches a new design it
# hands that design to the engine and waits; the engine's next step lets it
# continue:
#
#     engine thread                          optimiser thread
#     -------------                          ----------------
#     update(x0)  ── start ───────────────>  plugins.minimize(f, g, ..., callback)
#                 <── iterate(x1) ─────────  callback(x1)   (waits)
#     draw x1, check stopping rule
#     update(x1)  ── continue ────────────>  ... more evaluations ...
#                 <── iterate(x2) ─────────  callback(x2)   (waits)
#     ...
#     stop / Stop button: close() ── stop ─> callback raises, library unwinds
#                 <── done(verdict) ───────  or the library finishes by itself
#
# Only one thread ever runs at a time — the other is always waiting on a
# queue — so the model needs no locking.
#
# A library that reports progress per iteration calls `iterate` from its
# callback.  One with no such hook (NLopt) calls it from its objective wrapper,
# once per evaluation; one that reports nothing until the end never calls it,
# and the engine receives the final design as a single step.  `reports` says
# which, so the GUI can show it.

import queue
import threading
from dataclasses import dataclass

import numpy as np

from toporia.framework.parts.updater import Updater


@dataclass
class Verdict:
    """What the optimiser itself says about how it ended.

    success     : the library's own success flag, or None if it has none
    message     : its termination message
    x           : the final free variables
    iterations  : its own iteration count, when it reports one
    evaluations : its own function-evaluation count, when it reports one
    """
    success: bool | None
    message: str
    x: np.ndarray
    iterations: int | None = None
    evaluations: int | None = None


class _Stop(BaseException):
    """Raised inside the optimiser thread to unwind the library when the engine stops.

    A BaseException, so a library that catches Exception in its callback
    handling does not swallow it.
    """


class ExternalOptimizer(Updater):
    """An Updater for an optimiser that runs its own loop.  Subclasses implement run().

    Write run(flat, x0, iterate) as a plain call into the library: use the flat
    view's f, df, g, dg (or g_geq, dg_geq), call iterate(x) wherever the library
    reports a new design, and return a Verdict.  Everything else — the thread,
    the hand-over, stopping, recording the verdict — is done here.
    """

    flat_view = True
    own_loop = True
    #: Where the library calls iterate(): "iteration", "evaluation", or "final" (never).
    reports = "iteration"
    #: Seconds to wait for the library to unwind after a stop.
    stop_timeout = 10.0

    def run(self, flat, x0, iterate):
        """Run the library from x0 (free variables) to the end; return a Verdict."""
        raise NotImplementedError(f"{type(self).__name__} must implement run()")

    # ── The Updater interface ─────────────────────────────────────────────────

    def initialize(self, model, settings):
        self.settings = settings
        self.flat_problem(model)
        self._thread = None
        self._to_engine = queue.Queue()
        self._to_optimiser = queue.Queue()
        self._waiting = False      # the optimiser thread is parked in iterate()
        self.verdict = None
        self.finished = False      # the library has returned
        self._settled = False      # ... and the engine has evaluated its answer

    def update(self, x, evaluation, completed):
        flat = self.flat
        if self.finished:
            # One step after the library returned: the engine has just evaluated
            # its answer, so the run can end on the answer's own numbers.
            self._settled = True
            return x
        flat.remember(x, evaluation)
        if self._thread is None:
            self._thread = threading.Thread(target=self._main, args=(flat.reduce(x),),
                                            name=f"toporia-{self.name}", daemon=True)
            self._thread.start()
        else:
            self._waiting = False
            self._to_optimiser.put("continue")

        kind, payload = self._to_engine.get()
        if kind == "iterate":
            return flat.expand(payload)
        self.finished = True
        if kind == "error":
            raise payload
        self.verdict = payload
        return flat.expand(payload.x)

    def cached_evaluation(self, design):
        """The library usually evaluated the design it just handed over; reuse that."""
        return self.flat.cached(self.flat.reduce(design))

    def is_converged(self, change):
        return self._settled

    def convergence_reason(self):
        if self.verdict is None:
            return None
        return f"{self.label} finished: {self.verdict.message}"

    def report(self):
        """The optimiser's own verdict, for run.json and the console."""
        if self.verdict is None:
            return {"optimiser": self.label, "finished": False,
                    "message": "stopped by Toporia before the optimiser finished"}
        verdict = self.verdict
        return {"optimiser": self.label, "finished": True, "success": verdict.success,
                "message": verdict.message, "iterations": verdict.iterations,
                "evaluations": verdict.evaluations}

    def close(self):
        """Stop the optimiser thread if it is still running; wait for it to unwind."""
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        if self._waiting:
            self._to_optimiser.put("stop")
        thread.join(self.stop_timeout)

    # ── The optimiser thread ──────────────────────────────────────────────────

    def _main(self, x0):
        try:
            verdict = self.run(self.flat, x0, self._iterate)
        except _Stop:
            return                       # the engine stopped first; nobody is waiting
        except BaseException as error:   # noqa: BLE001 — handed to the engine thread
            self._to_engine.put(("error", error))
            return
        self._to_engine.put(("done", verdict))

    def _iterate(self, x):
        """Called by the library with a new design: hand it over, wait for the go-ahead."""
        self._waiting = True
        self._to_engine.put(("iterate", np.array(x, dtype=float)))
        if self._to_optimiser.get() == "stop":
            raise _Stop()
