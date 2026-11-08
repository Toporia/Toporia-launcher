"""Research companion: Geometry projection capsule bars."""

from ._research_batch3 import metadata, recipe

CASE_ID = "geometry_projection"
NAME, ABOUT, REFERENCE, DESCRIPTION = metadata(CASE_ID)
ORDER = 326


def scenario():
    return recipe(CASE_ID)[0]


def solver():
    return recipe(CASE_ID)[1]
