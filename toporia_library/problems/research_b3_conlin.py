"""Research companion: CONLIN mixed variables."""

from ._research_batch3 import metadata, recipe

CASE_ID = "conlin"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 306


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
