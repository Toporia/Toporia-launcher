# plugins/postprocessors/connectivity.py — is the structure in one piece, from the loads to the supports?
#
# The black-and-white design (from the threshold when one ran, else
# density >= 0.5) is split into pieces of elements that share an edge.
# Elements touching only at a corner carry no load between them in a Q4
# model, so they do not count as joined.  A piece that touches no support
# floats: its material does nothing.  The check passes when every load
# touches a piece that also touches a support.
#
# connectivity.png shows the design with the floating material in red.

import numpy as np
from PIL import Image
from scipy import ndimage

from toporia.framework.parts.postprocess import PostProcessor


def touching(node_mask):
    """The elements that have at least one of the marked nodes as a corner."""
    n = np.asarray(node_mask, dtype=bool)
    return n[:-1, :-1] | n[:-1, 1:] | n[1:, :-1] | n[1:, 1:]


class Connectivity(PostProcessor):
    """Pieces of the black-and-white design, floating material, and load paths."""

    name = "connectivity"
    label = "Connectivity check"
    order = 20
    table_metrics = ("pieces", "floating_fraction", "loads_connected")

    def process(self, result):
        problem = result.problem
        solid = result.solid()
        pieces, count = ndimage.label(solid)          # edge-sharing elements form one piece
        supports = touching(problem.fixed_nodes | problem.fixed_x_nodes | problem.fixed_y_nodes)
        supported = set(np.unique(pieces[supports & solid]).tolist()) - {0}
        floating = solid & ~np.isin(pieces, sorted(supported))

        load_sets = list(getattr(problem, "load_node_sets", [])) or [problem.load_nodes]
        loads_connected = all(
            bool(set(np.unique(pieces[touching(nodes) & solid]).tolist()) & supported) for nodes in load_sets)

        picture = np.stack([1.0 - solid] * 3, axis=-1)
        picture[floating] = (0.85, 0.15, 0.15)
        Image.fromarray((np.flipud(picture) * 255).astype(np.uint8), mode="RGB").save(
            result.file("connectivity.png"))
        return {"pieces": int(count), "floating_fraction": float(floating.sum() / max(solid.sum(), 1)),
                "loads_connected": loads_connected}
