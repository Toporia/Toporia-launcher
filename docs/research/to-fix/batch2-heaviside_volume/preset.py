"""Quarantined companion recipe: not discovered as a selectable GUI preset."""

from toporia.plugins.problems._research_batch2 import metadata, recipe

CASE_ID = "heaviside_volume"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
