"""Load nl-to-swmm models (JSON schema or .inp) into a normalized pipe list.

The nl-to-swmm JSON schema stores:
  - conduits: name, from_node, to_node, length_m, roughness_manning_n,
              in_offset_m, out_offset_m, shape, geom1_diameter_or_height_m, ...
  - junctions / outfalls: name, invert_elevation_m
Slope is NOT stored explicitly, so we derive it from node inverts + offsets.
Diameter is stored in METERS; the checker works in millimetres.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Pipe:
    name: str
    from_node: str
    to_node: str
    length_m: float
    diameter_mm: float
    shape: str = "CIRCULAR"
    roughness_n: float = 0.013
    in_offset_m: float = 0.0
    out_offset_m: float = 0.0
    invert_from_m: Optional[float] = None
    invert_to_m: Optional[float] = None
    # Optional post-simulation values (fill ratio / velocity checks need these):
    sim_velocity_mps: Optional[float] = None
    sim_max_depth_m: Optional[float] = None
    extra: dict = field(default_factory=dict)

    @property
    def slope(self) -> Optional[float]:
        """Design slope derived from invert elevations and offsets (m/m)."""
        if self.invert_from_m is None or self.invert_to_m is None:
            return None
        drop = (self.invert_from_m + self.in_offset_m) - (self.invert_to_m + self.out_offset_m)
        if self.length_m <= 0:
            return None
        return drop / self.length_m


@dataclass
class Model:
    title: str
    pipes: list[Pipe]
    source: str  # "json" | "inp"


# --------------------------------------------------------------------------- #
# JSON (nl-to-swmm schema)
# --------------------------------------------------------------------------- #
def load_json_model(path_or_obj) -> Model:
    if isinstance(path_or_obj, (str, Path)):
        data = json.loads(Path(path_or_obj).read_text(encoding="utf-8"))
    else:
        data = path_or_obj

    inverts: dict[str, float] = {}
    for group in ("junctions", "outfalls", "storages", "dividers"):
        for n in data.get(group, []) or []:
            if "name" in n and "invert_elevation_m" in n:
                inverts[n["name"]] = float(n["invert_elevation_m"])

    pipes: list[Pipe] = []
    for c in data.get("conduits", []) or []:
        diam_m = float(c.get("geom1_diameter_or_height_m", 0.0))
        p = Pipe(
            name=c["name"],
            from_node=c.get("from_node", ""),
            to_node=c.get("to_node", ""),
            length_m=float(c.get("length_m", 0.0)),
            diameter_mm=diam_m * 1000.0,
            shape=c.get("shape", "CIRCULAR"),
            roughness_n=float(c.get("roughness_manning_n", 0.013)),
            in_offset_m=float(c.get("in_offset_m", 0.0)),
            out_offset_m=float(c.get("out_offset_m", 0.0)),
            invert_from_m=inverts.get(c.get("from_node", "")),
            invert_to_m=inverts.get(c.get("to_node", "")),
        )
        pipes.append(p)

    return Model(title=data.get("title", "untitled"), pipes=pipes, source="json")


# --------------------------------------------------------------------------- #
# .inp (EPA SWMM) — minimal section parser for CONDUITS / XSECTIONS / nodes
# --------------------------------------------------------------------------- #
def _iter_sections(text: str):
    section, rows = None, []
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].rstrip()  # strip inline comments
        if not line.strip():
            continue
        m = re.match(r"^\[(.+?)\]\s*$", line.strip())
        if m:
            if section is not None:
                yield section, rows
            section, rows = m.group(1).upper(), []
        elif section is not None:
            rows.append(line.split())
    if section is not None:
        yield section, rows


def load_inp_model(path: str | Path) -> Model:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    sections = {name: rows for name, rows in _iter_sections(text)}

    inverts: dict[str, float] = {}
    for sec in ("JUNCTIONS", "OUTFALLS", "STORAGE", "DIVIDERS"):
        for row in sections.get(sec, []):
            if len(row) >= 2:
                try:
                    inverts[row[0]] = float(row[1])
                except ValueError:
                    pass

    # XSECTIONS: Link Shape Geom1 Geom2 Geom3 Geom4 (Geom1 in project length units)
    xsect: dict[str, tuple[str, float]] = {}
    for row in sections.get("XSECTIONS", []):
        if len(row) >= 3:
            try:
                xsect[row[0]] = (row[1], float(row[2]))
            except ValueError:
                pass

    pipes: list[Pipe] = []
    # CONDUITS: Name FromNode ToNode Length Roughness InOffset OutOffset [InitFlow MaxFlow]
    for row in sections.get("CONDUITS", []):
        if len(row) < 5:
            continue
        name, fnode, tnode = row[0], row[1], row[2]
        shape, geom1_m = xsect.get(name, ("CIRCULAR", 0.0))
        pipes.append(Pipe(
            name=name,
            from_node=fnode,
            to_node=tnode,
            length_m=float(row[3]),
            diameter_mm=geom1_m * 1000.0,  # .inp written by nl-to-swmm uses metres
            shape=shape.upper(),
            roughness_n=float(row[4]),
            in_offset_m=float(row[5]) if len(row) > 5 else 0.0,
            out_offset_m=float(row[6]) if len(row) > 6 else 0.0,
            invert_from_m=inverts.get(fnode),
            invert_to_m=inverts.get(tnode),
        ))

    title = "untitled"
    if sections.get("TITLE"):
        title = " ".join(sections["TITLE"][0])
    return Model(title=title, pipes=pipes, source="inp")


def load_any(path: str | Path) -> Model:
    path = Path(path)
    if path.suffix.lower() == ".json":
        return load_json_model(path)
    return load_inp_model(path)
