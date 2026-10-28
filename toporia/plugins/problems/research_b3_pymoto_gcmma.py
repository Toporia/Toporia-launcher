"""Research companion: GCMMA through pyMOTO."""

from ._research_batch3 import metadata, recipe

CASE_ID = "pymoto_gcmma"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 302


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
