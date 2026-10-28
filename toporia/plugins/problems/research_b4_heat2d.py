"""Research companion: 2D heat conduction and thermal compliance."""

from ._research_batch4 import metadata, recipe

CASE_ID = "heat2d"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 401


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
