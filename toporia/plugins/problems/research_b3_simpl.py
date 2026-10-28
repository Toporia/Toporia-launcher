"""Research companion: SiMPL primal and latent steps."""

from ._research_batch3 import metadata, recipe

CASE_ID = "simpl"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 311


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
