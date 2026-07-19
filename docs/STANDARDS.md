# The standard snapshot & how to update it

All normative content lives in **one file**:
`swmm_compliance/standards/gb50014.json`. It is not the full PDF — it is a
curated table of the thresholds and clause numbers the checker needs. Editing
this file is the **only** thing required when the standard changes; no code
changes, nothing to rebuild.

---

## Why a local snapshot

- **Robust** — no dependency on an external website that could move or change layout.
- **Cheap** — the standard isn't sent to the API on every check (and it is cached).
- **Auditable** — every threshold and clause is in one explicit place, not
  scattered across formulas.
- **Trade-off** — it is a point-in-time copy, so it must be updated by hand when
  a new edition is issued (see below). Standards like GB 50014 change roughly
  once per 5–15 years, so this is infrequent.

---

## File structure

```jsonc
{
  "standard": {
    "code": "GB 50014-2021",
    "title_zh": "室外排水设计标准",
    "effective_date": "2021-10-01",
    "snapshot_date": "2026-07-19",     // when THIS file was last edited
    "disclaimer_en": "...",
    "official_sources": ["https://..."]
  },
  "rules": {
    "min_diameter":      { "clause": "4.2.3", "unit": "mm",  "by_class": { ... } },
    "min_slope":         { "clause": "4.2.3", "unit": "m/m", "by_class": { ... } },
    "design_fill_ratio": { "clause": "4.2.1", "unit": "h/D", "table_by_diameter": [ ... ] },
    "min_velocity":      { "clause": "4.2.4", "unit": "m/s", "by_class": { ... } },
    "max_velocity":      { "clause": "4.2.5", "unit": "m/s", "by_material": { ... } }
  }
}
```

Each rule carries `verify_against_official: true` — a reminder that the clause
number was transcribed from secondary sources and should be confirmed against
the official PDF. Clear the flag once you've verified it.

### Network classes (`by_class`)

| Key | Chinese | Meaning | Notes |
|---|---|---|---|
| `sewage` | 污水管 | foul/industrial wastewater | partial-fill; velocity ≥ 0.6 m/s; fill-ratio limit |
| `stormwater` | 雨水管 | rainwater only | full-bore; velocity ≥ 0.75 m/s |
| `combined` | 合流管 | sewage + stormwater | like stormwater |
| `inlet_connection` | 雨水口连接管 | gully → manhole | DN ≥ 200, slope 0.01 |

---

## How to update when the norm changes

### Case A — a threshold value changed

Example: min sewage velocity 0.6 → 0.5 m/s.

1. Open `swmm_compliance/standards/gb50014.json`.
2. Edit the number:
   ```jsonc
   "min_velocity": { "by_class": { "sewage": { "min_mps": 0.5 } } }
   ```
3. Bump `snapshot_date`.
4. Save. Clear the report cache so old Claude answers refresh:
   `rm -f .cache/llm_reports.json`.

Done — no code change.

### Case B — a clause number changed

Update the `clause` field of that rule (e.g. `"4.2.3"` → `"4.3.1"`) and clear the
cache. The new reference appears in every report automatically.

### Case C — a brand-new edition (e.g. GB 50014-2027)

Recommended: keep editions side by side.

1. Copy the file: `gb50014.json` → `gb50014-2027.json`.
2. Update `standard.code`, `effective_date`, `snapshot_date`, and the values.
3. Point the loader at it — either overwrite `gb50014.json`, or change
   `STANDARDS_PATH` in `swmm_compliance/rules.py`.

Keeping both lets old projects be checked against the old edition and new ones
against the new one — a common real-world need.

### Case D — a new parameter to check (structural change)

This is the only case that touches code. Add the rule to the JSON **and** a
`check_*` method in `swmm_compliance/rules.py` following the existing ones. The
JSON stays the single source of thresholds and clause text.

---

## Verifying clause numbers

The bundled numbers were taken from public sources (listed under
`standard.official_sources`). Before relying on them in production, cross-check
§4.2.x against the official text and set `verify_against_official: false` on each
rule you've confirmed.
