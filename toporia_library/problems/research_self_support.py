"""Research demonstration: Gaynor-Guest support."""

from ._research_batch2 import metadata, recipe

CASE_ID = "self_support"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 232


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
