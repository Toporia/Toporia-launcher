"""Research companion: MMA through NLopt."""

from ._research_batch3 import metadata, recipe

CASE_ID = "nlopt_mma"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 305


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
