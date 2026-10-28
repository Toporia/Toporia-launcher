"""Research companion: GCMMA through mmapy."""

from ._research_batch3 import metadata, recipe

CASE_ID = "mmapy_gcmma"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 304


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
