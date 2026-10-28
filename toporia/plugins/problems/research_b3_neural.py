"""Research companion: Neural coordinate density."""

from ._research_batch3 import metadata, recipe

CASE_ID = "neural"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 327


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
