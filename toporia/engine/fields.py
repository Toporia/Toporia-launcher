# engine/fields.py — what the finite-element analysis of a finished design looks like, field by field.
#
# analysis_fields(run, density) solves the run's physics once for the given design and
# returns the fields a person wants to look at in colour: the stress, the strain energy,
# the displacement or the temperature.  Nothing here optimises or writes files.
#
#   von Mises stress     elements with density ≥ 0.5, of solid material (how the material
#                        would be loaded in the made part), largest over the load cases
#   strain energy        ½ E(ρ) uₑᵀKₑuₑ per element, weighted over the load cases
#   displacement         magnitude of the mean nodal displacement of each solid element
#   temperature          mean nodal temperature of each element (heat conduction)
#
# A physics that does not provide one of these simply leaves it out.

from dataclasses import dataclass

import numpy as np


@dataclass
class Field:
    """One field over the design's elements, shaped like the density."""

    values: np.ndarray
    unit: str
    note: str = ""


def _von_mises(stress):
    """Von Mises stress from Voigt components: (σxx, σyy, τxy) in 2-D, six components in 3-D."""
    if stress.shape[-1] == 3:
        sxx, syy, txy = np.moveaxis(stress, -1, 0)
        return np.sqrt(sxx**2 - sxx * syy + syy**2 + 3 * txy**2)
    s = np.moveaxis(stress, -1, 0)
    normal = 0.5 * ((s[0] - s[1]) ** 2 + (s[1] - s[2]) ** 2 + (s[2] - s[0]) ** 2)
    return np.sqrt(normal + 3 * (s[3] ** 2 + s[4] ** 2 + s[5] ** 2))


def _per_element(engine, nodal, case, components):
    """Mean nodal value per element as a field shaped like the design; None if the engine has no table."""
    table = getattr(engine, "edof", None) if components > 1 else getattr(engine, "enodes", None)
    if table is None:
        return None
    values = nodal[table, case]                                    # (elements, nodes × components)
    if components > 1:
        values = values.reshape(len(table), -1, components)
        per_element = np.linalg.norm(values.mean(axis=1), axis=1)
    else:
        per_element = values.mean(axis=1)
    shape = tuple(engine.problem.shape)
    if hasattr(engine, "_field"):
        return engine._field(per_element)
    return per_element.reshape(shape, order=getattr(engine, "element_order", "C"))


def analysis_fields(run, density):
    """{name: Field} for the design `density` analysed with the run's own physics.

    An empty dict for a whole method that does not expose its physics, or when the design
    cannot be analysed (the reason is in the "" entry's note).
    """
    import contextlib
    import io

    from toporia.engine.loop import initialized_method

    density = np.asarray(density, dtype=float)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            method = initialized_method(run)
    except (ValueError, ImportError) as error:
        return {"": Field(np.zeros(0), "", f"Cannot analyse this design: {error}")}
    try:
        engine = getattr(getattr(method, "_model", None), "engine", None)
        if engine is None:
            return {}
        expected = tuple(engine.problem.shape)
        if density.shape != expected:
            return {"": Field(np.zeros(0), "", f"The design is {density.shape}, the run's mesh {expected}.")}
        state = engine.solve(density)
        weights = np.asarray(state.weights, dtype=float)
        cases = range(len(weights))
        several = " (largest over the load cases)" if len(weights) > 1 else ""
        fields = {}
        try:
            stress = np.max([_von_mises(np.asarray(engine.element_stress(state, c))) for c in cases], axis=0)
            fields["von Mises stress"] = Field(np.where(density >= 0.5, stress, np.nan), "MPa",
                                               "Solid-material stress where the design is solid (density ≥ 0.5)"
                                               + several + ".")
        except (NotImplementedError, AttributeError, ValueError):
            pass
        energies = getattr(state, "energies", None)
        material = getattr(engine, "material", None)
        U = getattr(state, "U", None)
        if energies is not None and material is not None and U is not None:
            scenario = run.scenario
            E = material.stiffness(density, scenario.E0, scenario.Emin)
            energy = sum(w * 0.5 * E * np.asarray(e) for w, e in zip(weights, energies, strict=True))
            fields["Strain energy"] = Field(energy, "N·mm", "½ E(ρ) uₑᵀKₑuₑ per element, weighted over the load cases.")
        if U is not None:
            components = len(engine.problem.shape)
            per_case = [_per_element(engine, U, c, components) for c in cases]
            if per_case and per_case[0] is not None:
                fields["Displacement"] = Field(np.where(density >= 0.5, np.max(per_case, axis=0), np.nan), "mm",
                                               "Magnitude of each solid element's mean nodal displacement"
                                               + several + ".")
        T = getattr(state, "T", None)
        if T is not None:
            per_case = [_per_element(engine, T, c, 1) for c in cases]
            if per_case and per_case[0] is not None:
                fields["Temperature"] = Field(np.max(per_case, axis=0), "K above the supports",
                                              "Mean nodal temperature of each element" + several + ".")
        return fields
    finally:
        close = getattr(method, "close", None)
        if close is not None:
            close()
