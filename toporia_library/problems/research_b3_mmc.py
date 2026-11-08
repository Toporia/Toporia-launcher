"""Research companion: MMC constant-thickness bars."""

from ._research_batch3 import metadata, recipe

CASE_ID = "mmc"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 322


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
