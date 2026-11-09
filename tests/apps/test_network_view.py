"""test_network_view.py — a truss is shown as its bars and nodes (To do item 10).

Over the 2-D density the canvas draws every bar (wider for a larger area, red in tension,
blue in compression) and the nodes; in 3-D the bars join the density cloud; an element
design can show its element grid.  Both are display options.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

NETWORK = {"nodes": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]], "bars": [[0, 1], [1, 2], [0, 2]],
           "areas": [1.0, 0.5, 1e-5], "forces": [2.0, -1.0, 0.0]}


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_a_truss_is_drawn_over_its_density_and_can_be_hidden(app):
    from matplotlib.collections import LineCollection

    from toporia_gui.canvas import COMPRESSION, TENSION, LiveCanvas
    from toporia_gui.display_options import DEFAULTS
    canvas = LiveCanvas()
    canvas.set_display(DEFAULTS)
    canvas.set_network(NETWORK, width=20.0)
    canvas.refresh(np.zeros((10, 20)), [1.0], 1)
    lines = [a for a in canvas._overlay if isinstance(a, LineCollection)]
    assert len(lines) == 1 and len(lines[0].get_segments()) == 2          # the vanishing bar is left out
    colours = {tuple(np.round(c[:3], 3)) for c in lines[0].get_colors()}
    from matplotlib.colors import to_rgb
    assert colours == {tuple(np.round(to_rgb(TENSION), 3)), tuple(np.round(to_rgb(COMPRESSION), 3))}
    # 10 mm at 1 mm per element: node (10, 10) sits at column 9.5, row 10 - 10 - 0.5.
    assert np.allclose(lines[0].get_segments()[1][1], [9.5, -0.5])

    canvas.set_display({**DEFAULTS, "network": False, "elements": True})
    grid = [a for a in canvas._overlay if isinstance(a, LineCollection)]
    assert len(grid) == 1 and len(grid[0].get_segments()) == 21 + 11       # element edges only


def test_a_space_truss_joins_the_density_cloud(app):
    from mpl_toolkits.mplot3d.art3d import Line3DCollection

    from toporia_gui.canvas import LiveCanvas
    from toporia_gui.display_options import DEFAULTS
    canvas = LiveCanvas()
    canvas.set_display(DEFAULTS)
    canvas.set_network({**NETWORK, "nodes": [[0, 0, 0], [10, 0, 0], [10, 10, 5]]}, width=20.0)
    canvas.refresh(np.full((4, 10, 20), 0.5), [1.0], 1)
    canvas.show_3d(np.full((4, 10, 20), 0.5), 1.0)
    assert any(isinstance(c, Line3DCollection) for c in canvas._ax_d.collections)
