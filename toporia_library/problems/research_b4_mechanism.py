"""Research companion: Compliant force inverter and port adjoint."""

from ._research_batch4 import metadata, recipe

CASE_ID = "mechanism"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 411


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
