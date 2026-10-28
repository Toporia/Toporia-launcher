"""Research companion: Saved-field 2D post-processing."""

from ._research_batch4 import metadata, recipe

CASE_ID = "post2d"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 417


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
