"""Research companion: PTO sensitivity-proxy variant."""

from ._research_batch3 import metadata, recipe

CASE_ID = "pto"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 313


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
