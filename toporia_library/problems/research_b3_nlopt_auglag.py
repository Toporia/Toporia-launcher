"""Research companion: Augmented Lagrangian through NLopt."""

from ._research_batch3 import metadata, recipe

CASE_ID = "nlopt_auglag"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 320


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
