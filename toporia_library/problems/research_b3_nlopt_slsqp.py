"""Research companion: SLSQP through NLopt."""

from ._research_batch3 import metadata, recipe

CASE_ID = "nlopt_slsqp"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 317


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
