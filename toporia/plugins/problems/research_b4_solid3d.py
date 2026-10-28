"""Research companion: 3D H8 elasticity."""

from ._research_batch4 import metadata, recipe

CASE_ID = "solid3d"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 400


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
