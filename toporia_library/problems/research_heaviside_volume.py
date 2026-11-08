"""Research demonstration: volume-preserving Heaviside projection."""

from ._research_batch2 import metadata, recipe

CASE_ID = "heaviside_volume"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 223


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
