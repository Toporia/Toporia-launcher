"""Research companion: BESO soft kill."""

from ._research_batch3 import metadata, recipe

CASE_ID = "beso"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 308


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
