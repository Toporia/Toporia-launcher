"""Research companion: Multiresolution Galerkin stiffness."""

from ._research_batch4 import metadata, recipe

CASE_ID = "multires"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 412


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
