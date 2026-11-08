"""Research companion: Saved-field STL solid export."""

from ._research_batch4 import metadata, recipe

CASE_ID = "post3d"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 418


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
