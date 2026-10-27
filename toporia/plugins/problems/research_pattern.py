"""Research demonstration: Repeated layout pattern."""

from ._research_batch2 import metadata, recipe

CASE_ID = "pattern"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 229


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
