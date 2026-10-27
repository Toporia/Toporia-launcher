"""Research demonstration: PDE filter: top82 Fig. 4(b)."""

from ._research_batch2 import metadata, recipe

CASE_ID = "pde"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 220


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
