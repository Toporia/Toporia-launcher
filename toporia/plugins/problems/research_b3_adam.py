"""Research companion: Adam moments and volume penalty."""

from ._research_batch3 import metadata, recipe

CASE_ID = "adam"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 312


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
