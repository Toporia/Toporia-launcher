"""Research demonstration: Directional PDE filter."""

from ._research_batch2 import metadata, recipe

CASE_ID = "pde_anisotropic"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 221


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
