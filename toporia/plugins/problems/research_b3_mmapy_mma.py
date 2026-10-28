"""Research companion: MMA through mmapy."""

from ._research_batch3 import metadata, recipe

CASE_ID = "mmapy_mma"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 303


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
