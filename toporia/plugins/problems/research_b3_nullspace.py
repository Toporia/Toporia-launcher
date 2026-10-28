"""Research companion: Null-space gradient flow."""

from ._research_batch3 import metadata, recipe

CASE_ID = "nullspace"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 321


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
