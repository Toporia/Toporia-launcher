"""Research demonstration: Geometric beta continuation."""

from ._research_batch2 import metadata, recipe

CASE_ID = "schedule_geometric"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 238


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
