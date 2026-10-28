"""Research companion: Geometric solid and void length indicators."""

from ._research_batch4 import metadata, recipe

CASE_ID = "minimum_length"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 415


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
