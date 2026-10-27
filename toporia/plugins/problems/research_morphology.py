"""Research demonstration: Morphology: four operations."""

from ._research_batch2 import metadata, recipe

CASE_ID = "morphology"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 224


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
