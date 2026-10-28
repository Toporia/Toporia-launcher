"""Research companion: Heat conduction through pyMOTO."""

from ._research_batch4 import metadata, recipe

CASE_ID = "heat_pymoto"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 404


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
