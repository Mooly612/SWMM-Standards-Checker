# Input formats

The checker accepts **one file per run**: nl-to-swmm JSON, or an EPA SWMM `.inp`.

Two things to remember for both formats:

- **Diameter is in metres** (`geom1_diameter_or_height_m` / XSECTIONS Geom1) and
  converted to mm internally. `0.30` means DN300.
- **Slope is not stored — it is computed** as
  `((invert_from + in_offset) − (invert_to + out_offset)) / length`.
  So a conduit’s `from_node`/`to_node` must exist among the junctions/outfalls,
  otherwise slope can’t be derived and that check is reported as “info”.

---

## 1. JSON (nl-to-swmm schema)

### Conduits

| Field | Type | Unit | Notes |
|---|---|---|---|
| `name` | str | — | required |
| `from_node` | str | — | must match a node name |
| `to_node` | str | — | must match a node name |
| `length_m` | float | m | > 0 |
| `geom1_diameter_or_height_m` | float | **m** | diameter for circular |
| `shape` | str | — | `CIRCULAR` (default), `RECT_CLOSED`, `TRAPEZOIDAL` |
| `roughness_manning_n` | float | — | default `0.013`; used to infer material/velocity |
| `in_offset_m` / `out_offset_m` | float | m | default `0.0` |

### Nodes (junctions & outfalls)

| Field | Type | Unit |
|---|---|---|
| `name` | str | — |
| `invert_elevation_m` | float | m |
| `max_depth_m` (junctions) | float | m |

Storage nodes and dividers are also read for invert elevations if present.

### Minimal valid file

```json
{
  "title": "one pipe",
  "junctions": [{"name": "J1", "invert_elevation_m": 100.0, "max_depth_m": 2.0}],
  "outfalls":  [{"name": "O1", "invert_elevation_m": 99.2}],
  "conduits":  [{"name": "C1", "from_node": "J1", "to_node": "O1",
                 "length_m": 200, "geom1_diameter_or_height_m": 0.40,
                 "roughness_manning_n": 0.013}]
}
```

---

## 2. INP (EPA SWMM)

Only the sections needed for pipe checks are parsed; the rest is ignored.

```ini
[JUNCTIONS]
;;Name  Elevation  MaxDepth
J1      100.0      2.0

[OUTFALLS]
;;Name  Elevation  Type
O1      99.2       FREE

[CONDUITS]
;;Name  From  To   Length  Roughness  InOffset  OutOffset
C1      J1    O1   200     0.013      0         0

[XSECTIONS]
;;Link  Shape     Geom1  Geom2  Geom3  Geom4
C1      CIRCULAR  0.40   0      0      0
```

- Comment lines (`;`) and inline comments are stripped.
- `Geom1` in `[XSECTIONS]` is the diameter **in metres** (as written by nl-to-swmm).
- Slope is again computed from junction/outfall elevations.

---

## What is NOT checked from the file alone

**Fill ratio (设计充满度, §4.2.1)** needs the actual flow depth, which only comes
from running the SWMM simulation. Until you attach simulation output
(`sim_max_depth_m` on a pipe), this check is skipped. Diameter, slope and a
full-bore Manning velocity are all derived from the static file.
