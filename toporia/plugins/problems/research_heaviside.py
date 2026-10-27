"""Research demonstration: Heaviside projection curves."""

from ._research_batch2 import metadata, recipe

CASE_ID = "heaviside"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 222


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
