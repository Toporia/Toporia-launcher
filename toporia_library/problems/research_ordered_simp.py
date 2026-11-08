"""Research demonstration: Ordered SIMP: formula audit."""

from ._research_batch2 import metadata, recipe

CASE_ID = "ordered_simp"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 234


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
