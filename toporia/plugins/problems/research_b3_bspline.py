"""Research companion: B-spline density coefficients."""

from ._research_batch3 import metadata, recipe

CASE_ID = "bspline"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 325


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
