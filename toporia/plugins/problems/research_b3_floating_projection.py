"""Research companion: Floating projection update."""

from ._research_batch3 import metadata, recipe

CASE_ID = "floating_projection"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 310


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
