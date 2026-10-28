"""Research companion: Minimum volume with aggregate stress."""

from ._research_batch4 import metadata, recipe

CASE_ID = "stress_volume"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 413


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
