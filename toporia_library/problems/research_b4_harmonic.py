"""Research companion: Undamped harmonic dynamic compliance."""

from ._research_batch4 import metadata, recipe

CASE_ID = "harmonic"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 407


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
