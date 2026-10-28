"""Research companion: Linearized buckling factors."""

from ._research_batch4 import metadata, recipe

CASE_ID = "buckling"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 409


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
