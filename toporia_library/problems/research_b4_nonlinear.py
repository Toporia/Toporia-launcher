"""Research companion: Large-displacement elasticity and end compliance."""

from ._research_batch4 import metadata, recipe

CASE_ID = "nonlinear"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 410


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
