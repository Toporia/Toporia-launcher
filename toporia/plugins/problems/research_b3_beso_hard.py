"""Research companion: BESO hard kill."""

from ._research_batch3 import metadata, recipe

CASE_ID = "beso_hard"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 309


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
