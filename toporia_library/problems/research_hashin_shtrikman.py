"""Research demonstration: SIMP and HS envelope."""

from ._research_batch2 import metadata, recipe

CASE_ID = "hashin_shtrikman"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 236


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
