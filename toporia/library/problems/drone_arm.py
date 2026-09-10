# drone_arm.py — topology optimisation problem for the drone arm bracket
#
# Domain:  200 mm × 85 mm rectangular plate
# Fixed:   two central mounting holes (bolted to the frame)
# Load:    eight motor-attachment holes, equal +x and +y load cases

from toporia.core.config import HoleConfig, LoadCase, TopOptConfig


def get_config() -> TopOptConfig:
    return TopOptConfig(
        Lx=200.0,
        Ly=85.0,
        m=1.0,

        holes=[
            # Frame-mount holes — clamped (all DOFs fixed)
            HoleConfig(cx=85.1,  cy=75.0, r_void=3.0, r_passive=6.0, kind="fixed"),
            HoleConfig(cx=115.6, cy=75.0, r_void=3.0, r_passive=6.0, kind="fixed"),
            # Motor-attachment holes — load applied here
            HoleConfig(cx=7.9,   cy=17.6, r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=15.2,  cy=8.9,  r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=16.6,  cy=24.9, r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=23.8,  cy=16.2, r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=192.8, cy=17.6, r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=185.6, cy=8.9,  r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=184.2, cy=24.9, r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=176.9, cy=16.2, r_void=3.0, r_passive=6.0, kind="load"),
        ],

        load_cases=[
            LoadCase(Fmag=1.0, Fa=0.0,  weight=0.5),
            LoadCase(Fmag=1.0, Fa=90.0, weight=0.5),
        ],

        volfrac=0.5,
        filter_specs=[{"type": "density"}],
        max_iter=100,
        tol=0.01,
    )
