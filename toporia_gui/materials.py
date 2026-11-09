# toporia_gui/materials.py — common engineering materials, for the material presets.
#
# Units are those of the whole program: millimetres, newtons, so stresses and Young's
# modulus in N/mm² = MPa.  The values are typical room-temperature figures for design
# studies, not certified data: E for polymers and printed parts varies with grade,
# print orientation and moisture, so check a datasheet before relying on a number.

#: name -> (Young's modulus E [MPa], Poisson's ratio ν, density [g/cm³], note)
MATERIALS = {
    "Structural steel": (210_000.0, 0.30, 7.85, "e.g. S235/S355"),
    "Stainless steel": (193_000.0, 0.29, 8.00, "e.g. 304/316"),
    "Aluminium alloy": (70_000.0, 0.33, 2.70, "e.g. 6061-T6"),
    "Titanium alloy": (114_000.0, 0.34, 4.43, "Ti-6Al-4V"),
    "PE (HDPE)": (1_000.0, 0.42, 0.95, "high-density polyethylene"),
    "PA (nylon 6)": (2_500.0, 0.39, 1.14, "dry; lower when moist"),
    "PLA (printed)": (3_500.0, 0.36, 1.24, "FDM, in the print plane"),
    "Resin (SLA)": (2_500.0, 0.38, 1.18, "standard photopolymer"),
}

#: Void stiffness as a fraction of the solid's: keeps the stiffness matrix non-singular
#: at any modulus, so a design does not depend on the units E is given in.
VOID_RATIO = 1e-9


def matching_material(E0, nu):
    """The preset with this modulus and Poisson's ratio, or None for a custom material."""
    return next((name for name, (E, v, _, _) in MATERIALS.items()
                 if abs(E - E0) <= 1e-9 * E and abs(v - nu) < 1e-9), None)


def material_combo(on_pick):
    """A dropdown of the presets plus 'Custom'; picking one calls on_pick(E0, nu)."""
    from PySide6.QtWidgets import QComboBox
    combo = QComboBox()
    combo.addItem("Custom", None)
    for name, (E, nu, rho, note) in MATERIALS.items():
        combo.addItem(f"{name}  ·  E {E:,.0f} MPa, ν {nu:g}", name)
        combo.setItemData(combo.count() - 1, f"{name}: {note}; density {rho:g} g/cm³. Typical values; "
                                              "check a datasheet.", 3)        # Qt.ToolTipRole
    combo.setToolTip("Common materials, in MPa. Typical values for design studies; check a datasheet.")

    def picked(index):
        name = combo.itemData(index)
        if name is not None:
            E, nu, _, _ = MATERIALS[name]
            on_pick(E, nu)
    combo.currentIndexChanged.connect(picked)
    return combo
