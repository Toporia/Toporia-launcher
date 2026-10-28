"""Research companion: Natural frequencies and mode aggregation."""

from ._research_batch4 import metadata, recipe

CASE_ID = "dynamic"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 406


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
