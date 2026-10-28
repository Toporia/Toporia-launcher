"""Research companion: MMV superelliptical holes."""

from ._research_batch3 import metadata, recipe

CASE_ID = "mmv"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 324


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
