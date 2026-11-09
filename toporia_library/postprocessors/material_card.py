# toporia_library/postprocessors/material_card.py — a designed microstructure as a material to build with.
#
# After a unit-cell run (q4_periodic, h8_periodic) this computes the homogenised elasticity
# matrix C^H of the final design (toporia_library/physics/homogenisation.py, with the run's
# material law) and writes it to material.json, with its derived moduli and, in 2-D, the
# parameter set of the q4_anisotropic model, so a part can be designed in that material:
#
#     {"C": [[C11, C12, C13], ...], "bulk_modulus": κ, "shear_modulus": G,
#      "poisson_ratio": ν, "q4_anisotropic": {"C11": ..., "C12": ..., "C22": ..., "C33": ...}}
#
# with κ, G and ν as in toporia_library/responses/homogenised.py.  On a design that is not a unit
# cell its metrics are None and it writes nothing.

import json

import numpy as np

from toporia_core.framework.parts.postprocess import PostProcessor


class MaterialCard(PostProcessor):
    """The homogenised elasticity matrix of a designed unit cell, ready to build a part with."""

    name = "material_card"
    label = "Material card (homogenised stiffness)"
    use_when = ("After designing a microstructure: write its homogenised stiffness, and the settings that let the "
                "'2-D Q4 in a designed material' model build a part from it.")
    reference = "Toporia's own: the homogenised matrix of the final design, as a reusable material."
    order = 57
    dims = (2, 3)
    table_metrics = ("bulk_modulus", "shear_modulus", "poisson_ratio")

    def process(self, result):
        method = result.run.solver.method
        model = method.split("+")[0]
        if model not in ("q4_periodic", "h8_periodic"):
            return {"bulk_modulus": None, "shear_modulus": None, "poisson_ratio": None}
        from toporia_core.framework.parts.assembled import material_law
        from toporia_library.physics.homogenisation import H8PeriodicCell, Q4PeriodicCell
        engine = (Q4PeriodicCell if model == "q4_periodic" else H8PeriodicCell)()
        material = material_law(result.run.solver)
        material.setup(result.problem)
        engine.initialize(result.problem, {}, material)
        C = engine.homogenised(engine.solve(np.asarray(result.density, dtype=float)))
        d = 2 if len(C) == 3 else 3
        bulk = float(np.sum(C[:d, :d]) / d ** 2)
        shear = float(C[2, 2] if d == 2 else (C[3, 3] + C[4, 4] + C[5, 5]) / 3)
        poisson = float(np.mean([C[a, b] / (0.5 * (C[a, a] + C[b, b]))
                                 for a, b in ([(0, 1)] if d == 2 else [(0, 1), (0, 2), (1, 2)])]))
        card = {"C": np.round(C, 10).tolist(), "bulk_modulus": bulk, "shear_modulus": shear, "poisson_ratio": poisson}
        if d == 2:
            card["q4_anisotropic"] = {"C11": C[0, 0], "C12": C[0, 1], "C22": C[1, 1], "C33": C[2, 2],
                                      "C13": C[0, 2], "C23": C[1, 2]}
        result.file("material.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        return {"bulk_modulus": bulk, "shear_modulus": shear, "poisson_ratio": poisson}
