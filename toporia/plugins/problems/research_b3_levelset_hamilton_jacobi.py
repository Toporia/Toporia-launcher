"""Research companion: Hamilton-Jacobi level-set evolution."""

from ._research_batch3 import metadata, recipe

CASE_ID = "levelset_hamilton_jacobi"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 329


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
