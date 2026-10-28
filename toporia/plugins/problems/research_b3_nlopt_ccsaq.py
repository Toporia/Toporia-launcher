"""Research companion: CCSAQ through NLopt."""

from ._research_batch3 import metadata, recipe

CASE_ID = "nlopt_ccsaq"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 319


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
