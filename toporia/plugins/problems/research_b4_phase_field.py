"""Research companion: Diffuse-interface energy and compliance."""

from ._research_batch4 import metadata, recipe

CASE_ID = "phase_field"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 416


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
