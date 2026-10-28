"""Research companion: TOBS integer design steps."""

from ._research_batch3 import metadata, recipe

CASE_ID = "tobs"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 314


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
