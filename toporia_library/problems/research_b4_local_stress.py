"""Research companion: Local stress penalties and multiplier fields."""

from ._research_batch4 import metadata, recipe

CASE_ID = "local_stress"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 414


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
