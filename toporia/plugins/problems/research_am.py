"""Research demonstration: AM overhang filter."""

from ._research_batch2 import metadata, recipe

CASE_ID = "am"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 225


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
