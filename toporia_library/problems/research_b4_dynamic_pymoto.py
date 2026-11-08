"""Research companion: Vibration through pyMOTO."""

from ._research_batch4 import metadata, recipe

CASE_ID = "dynamic_pymoto"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 405


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
