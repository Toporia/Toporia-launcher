"""The scenario preview makes both port springs and desired motion visible."""

from matplotlib.figure import Figure

from toporia.apps.gui.preview import draw_problem
from toporia.plugins.problems import get_run


def test_springs_and_desired_output_are_drawn_from_the_actual_scenario():
    scenario = get_run("Force Inverter").scenario
    ax = Figure().subplots()
    labels = draw_problem(ax, scenario)
    assert "Ground spring" in labels
    assert "Desired output" in labels
    assert sum(text.get_text().startswith("k=") for text in ax.texts) == 2
