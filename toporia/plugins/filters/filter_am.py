# filter_am.py — AMFilter (additive manufacturing overhang constraint)
#
# Direct port of AMfilter.m by Langelaar (2016),
# DOI: 10.1007/s00158-016-1522-2
#
# Models a layer-by-layer deposition process.  Each layer is constrained to be
# no denser than what is supportable by the layer directly below it.
# "Supportable" means: the smooth-maximum of a neighbourhood of elements in the
# row below must be at least as large as the current element's density.
#
# The neighbourhood width is controlled by the overhang angle θ:
#   θ = 0°  → Ns = 1 (pillar only — element must sit directly on support below)
#   θ = 45° → Ns = 3 (standard — default, looks ±1 element to each side)
#   θ = 60° → Ns = 3 (still 3 — tan(60°)=1.73, floor=1, half=1)
#   θ ≥ 90° → no constraint (all overhangs allowed, filter is identity)
#   In general: half = floor(tan(θ)), Ns = 1 + 2·half
#
# Display orientation (canvas.py applies np.flipud so row 0 = IMAGE BOTTOM):
#
#   direction=0   — base at IMAGE BOTTOM, build UP ↑   (most common FDM/SLS)
#   direction=90  — base at IMAGE LEFT,   build RIGHT →
#   direction=180 — base at IMAGE TOP,    build DOWN ↓
#   direction=270 — base at IMAGE RIGHT,  build LEFT ←
#
# The design is rotated with np.rot90 so that the base is always at the last
# row (xr[nely-1,:]) during computation, then rotated back.
#
# Forward pass: smooth min of (x[i], Xi[i]) where Xi[i] is the smooth max of
#   the Ns neighbours in the row below.
# Backward pass: full adjoint as derived in Langelaar (2016) §3, generalised
#   to arbitrary Ns.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.filter import Filter

# Integer direction → internal letter mapping (image coordinates, post flipud).
_DIR_MAP = {0: 'S', 90: 'W', 180: 'N', 270: 'E'}


class AMFilter(Filter):
    """Additive manufacturing overhang filter (Langelaar 2016).

    Parameters
    ----------
    direction : int (0 / 90 / 180 / 270) or legacy str ('S'/'N'/'W'/'E').
        0   = base at image bottom, build up   ↑
        90  = base at image left,   build right →
        180 = base at image top,    build down  ↓
        270 = base at image right,  build left  ←
    overhang_angle : float, degrees.
        Maximum allowable overhang angle from vertical (0–90).
        0   = pillars only (each element must be directly above its support).
        45  = standard 45° rule (default, Ns=3 neighbours).
        ≥90 = no constraint (filter is identity, all overhangs permitted).
    """

    # Smooth max/min sharpness parameters (from the paper, fixed).
    _P    = 40
    _ep   = 1e-4
    _xi_0 = 0.5

    name = "am"
    label = "AM overhang filter"
    order = 40
    params = (
        Param("direction", 0, "Direction", "Build direction, as seen in the density image.",
              choices=((0, "0° — base bottom, build up ↑"),
                       (90, "90° — base left,  build right →"),
                       (180, "180° — base top,  build down ↓"),
                       (270, "270° — base right, build left ←"))),
        Param("overhang_angle", 45.0, "Overhang",
              "Largest printable overhang. 0 = pillars only, 45 = the standard rule, 89.9 = nearly unconstrained.",
              min=0.0, max=89.9, step=5.0, decimals=1, units="°"),
    )

    def __init__(self, direction=0, overhang_angle=45.0):
        # Accept int (0/90/180/270) or legacy letter.
        if isinstance(direction, int):
            if direction not in _DIR_MAP:
                raise ValueError(
                    f"direction must be 0, 90, 180, or 270 — got {direction!r}")
            self.direction = _DIR_MAP[direction]
        elif isinstance(direction, str):
            d = direction.upper()
            if d not in ('S', 'N', 'W', 'E'):
                raise ValueError(
                    f"direction must be S/N/W/E or 0/90/180/270 — got {direction!r}")
            self.direction = d
        else:
            raise ValueError(f"direction must be int or str — got {type(direction)}")

        self.overhang_angle = float(overhang_angle)
        # Compute the neighbourhood half-width from the angle.
        # half=0 → Ns=1 (pillars), half=1 → Ns=3 (45°), half=2 → Ns=5, …
        if self.overhang_angle >= 90.0:
            self._half = None   # identity — no constraint
        else:
            # Add 1e-9 before truncating to avoid floating-point edge cases
            # (e.g. tan(45°) computes as 0.9999…999 → would floor to 0 without it).
            self._half = max(0, int(np.tan(np.radians(self.overhang_angle)) + 1e-9))

    def setup(self, problem, solver): pass

    def _nrot(self):
        # CCW 90° rotations to bring the baseplate to xr[nely-1,:].
        # Calibrated to image coordinates (after canvas.py flipud):
        #   S → row 0 (image bottom) becomes xr base → nRot=2
        #   N → row nely-1 (image top) already at base → nRot=0
        #   W → col 0 (image left) rotated to base row → nRot=3
        #   E → col nelx-1 (image right) rotated to base row → nRot=1
        return {'S': 2, 'N': 0, 'W': 3, 'E': 1}[self.direction]

    def forward(self, x):
        if self._half is None:          # angle ≥ 90°: no constraint
            return x.copy()

        nRot       = self._nrot()
        xr         = np.rot90(x, nRot)
        nely, nelx = xr.shape

        half = self._half
        Ns   = 1 + 2 * half
        P    = self._P;   ep   = self._ep;   xi_0 = self._xi_0

        # Q, SHIFT, BACKSHIFT from the paper (generalised to arbitrary Ns).
        # For Ns=1: log(1)/log(xi_0) = 0, so Q = P exactly.
        Q        = P + np.log(Ns) / np.log(xi_0)
        SHIFT    = 100.0 * np.finfo(float).tiny ** (1.0 / P)
        BACKSHIFT = 0.95 * Ns ** (1.0 / Q) * SHIFT ** (P / Q)

        xi   = np.zeros_like(xr)
        keep = np.zeros_like(xr)
        sq   = np.zeros_like(xr)
        Xi   = np.zeros_like(xr)

        # Baseplate row — copied directly.
        xi[nely - 1, :] = xr[nely - 1, :]

        for i in range(nely - 2, -1, -1):
            # Build the padded neighbourhood vector for row i+1.
            cbr = np.concatenate([[0.0] * half, xi[i + 1, :], [0.0] * half]) + SHIFT
            # Smooth maximum of Ns neighbours → supportable density Xi[i].
            k_sum = np.zeros(nelx)
            for k in range(Ns):
                k_sum += cbr[k:k + nelx] ** P
            keep[i, :] = k_sum
            Xi[i, :]   = keep[i, :] ** (1.0 / Q) - BACKSHIFT
            sq[i, :]   = np.sqrt((xr[i, :] - Xi[i, :]) ** 2 + ep)
            # Smooth minimum of blueprint x and supportable Xi.
            xi[i, :]   = 0.5 * ((xr[i, :] + Xi[i, :]) - sq[i, :] + np.sqrt(ep))

        self._saved = dict(
            xr=xr, xi=xi, keep=keep, sq=sq, Xi=Xi,
            nRot=nRot, nely=nely, nelx=nelx, Q=Q,
            half=half, Ns=Ns,
        )
        return np.rot90(xi, -nRot)

    def backward(self, x_in, sensitivity):
        if self._half is None:
            return sensitivity.copy()

        sv   = self._saved
        xr   = sv['xr'];    xi   = sv['xi']
        keep = sv['keep'];  sq   = sv['sq'];   Xi   = sv['Xi']
        nRot = sv['nRot'];  nely = sv['nely']; nelx = sv['nelx']
        Q    = sv['Q'];     half = sv['half']; Ns   = sv['Ns']
        P    = self._P
        SHIFT = 100.0 * np.finfo(float).tiny ** (1.0 / P)

        dfxi = np.rot90(sensitivity, nRot)
        dfx  = np.zeros_like(xr)
        lam  = np.zeros(nelx)

        for i in range(nely - 1):
            dsmindx  = 0.5 * (1.0 - (xr[i, :] - Xi[i, :]) / sq[i, :])
            dsmindXi = 1.0 - dsmindx

            cbr = np.concatenate([[0.0] * half, xi[i + 1, :], [0.0] * half]) + SHIFT
            dmx = np.zeros((Ns, nelx))
            for j in range(Ns):
                dmx[j, :] = ((P / Q) * keep[i, :] ** (1.0 / Q - 1.0)
                              * cbr[j:j + nelx] ** (P - 1.0))

            # Propagate adjoint lam through the smooth-max neighbourhood.
            # For each stencil position k (offset = k - half relative to center):
            #   sensitivity at element f in row i+1 gets contribution from
            #   element e = f - offset in row i.
            incoming = (dfxi[i, :] + lam) * dsmindXi
            lam_new  = np.zeros(nelx)
            for k in range(Ns):
                offset = k - half
                if offset == 0:
                    lam_new += incoming * dmx[k, :]
                elif offset < 0:          # element in row i looks left: e → e+|offset|
                    lam_new[:nelx + offset] += incoming[-offset:] * dmx[k, -offset:]
                else:                     # element in row i looks right: e → e-offset
                    lam_new[offset:] += incoming[:nelx - offset] * dmx[k, :nelx - offset]

            dfx[i, :] = dsmindx * (dfxi[i, :] + lam)
            lam       = lam_new

        dfx[nely - 1, :] = dfxi[nely - 1, :] + lam
        return np.rot90(dfx, -nRot)
