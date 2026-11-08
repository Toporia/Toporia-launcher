"""Research demonstration: RAMP stiffness curves."""

from ._research_batch2 import metadata, recipe

CASE_ID = "ramp"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 233


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
