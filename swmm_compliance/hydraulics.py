"""Hydraulic helpers. Kept deliberately simple and explicit.

Full-flow Manning velocity for a circular pipe running full:
    v_full = (1/n) * R^(2/3) * S^(1/2),  with R = D/4
This is a pipe-capacity proxy used when no simulation output is available.
For the true design velocity (at the design fill degree) use the value from
a pyswmm run and store it on Pipe.sim_velocity_mps.
"""
from __future__ import annotations

import math
from typing import Optional


def full_flow_velocity_mps(diameter_mm: float, slope: float, n: float) -> Optional[float]:
    if diameter_mm <= 0 or n <= 0 or slope is None or slope <= 0:
        return None
    d = diameter_mm / 1000.0
    r = d / 4.0
    return (1.0 / n) * (r ** (2.0 / 3.0)) * math.sqrt(slope)


def infer_material(n: float) -> str:
    """Rough material family from Manning's n (for the metal/non-metal cap)."""
    # Metal pipes have low n (~0.011-0.013 for steel/ductile). SWMM defaults and
    # concrete/plastic sit here too, so we treat almost everything as non-metal
    # unless n is very low. Users can override in the UI.
    return "metal" if n <= 0.010 else "non_metal"


def is_plastic(n: float) -> bool:
    """Plastic pipes (PVC/HDPE) have low roughness; used for min-slope selection."""
    return n <= 0.012
