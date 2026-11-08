"""Research companion: MMA: local one-budget variant."""

from ._research_batch3 import metadata, recipe

CASE_ID = "mma"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 300


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
