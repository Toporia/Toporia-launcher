# Figure preset checklist

- Function IDs and implementation files:
- Paper title / DOI / accessible primary source:
- Figure, panel and manuscript/published version:
- Question the figure answers:
- Geometry, coordinates, mesh and discretization:
- Loads, supports, material constants and units:
- Initial design, optimizer, moves, filters and continuation:
- Objective, constraints, stopping rule and safety cap:
- Main equations, symbol definitions and implementation differences:
- Expected measurements and comparison tolerances:
- Rerun command and optional dependencies:
- Author-source identity/hash if used:
- Generated field, curves and comparison report:
- Separate native-code / paper-visual / paper-numerical status:
- Limitations, unresolved discrepancies and next check:

Implement the recipe as a discovered `plugins/problems/paper_*.py` module with
NAME, ABOUT, REFERENCE, DESCRIPTION, scenario() and solver(). Reuse implemented
numerics; do not copy an algorithm into the preset or invent missing settings.
