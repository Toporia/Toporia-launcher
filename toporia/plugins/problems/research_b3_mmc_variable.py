"""Research companion: MMC variable-thickness bars."""

from ._research_batch3 import metadata, recipe

CASE_ID = "mmc_variable"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 323


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
