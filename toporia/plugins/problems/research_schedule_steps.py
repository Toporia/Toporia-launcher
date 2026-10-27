"""Research demonstration: Equal-step continuation."""

from ._research_batch2 import metadata, recipe

CASE_ID = "schedule_steps"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 237


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
