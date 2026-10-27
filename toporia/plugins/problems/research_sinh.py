"""Research demonstration: SINH effective-cost curves."""

from ._research_batch2 import metadata, recipe

CASE_ID = "sinh"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 235


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
