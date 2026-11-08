"""Research demonstration: PDE machining shadows."""

from ._research_batch2 import metadata, recipe

CASE_ID = "machining"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 231


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
