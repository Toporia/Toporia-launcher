"""Research companion: OC with several multipliers."""

from ._research_batch3 import metadata, recipe

CASE_ID = "oc_multi"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 307


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
