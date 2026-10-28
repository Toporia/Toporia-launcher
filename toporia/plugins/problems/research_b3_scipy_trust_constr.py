"""Research companion: Trust-constr through SciPy."""

from ._research_batch3 import metadata, recipe

CASE_ID = "scipy_trust_constr"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 318


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
