"""Research companion: 3D H8 heat conduction."""

from ._research_batch4 import metadata, recipe

CASE_ID = "heat3d"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 402


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
