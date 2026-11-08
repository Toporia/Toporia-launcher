"""Research companion: Minimum eigenvalue constraint."""

from ._research_batch4 import metadata, recipe

CASE_ID = "frequency_limit"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 408


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
