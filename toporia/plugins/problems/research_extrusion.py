"""Research demonstration: Constant cross-section."""

from ._research_batch2 import metadata, recipe

CASE_ID = "extrusion"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 228


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
