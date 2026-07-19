# SWMM Compliance Checker (GB 50014-2021)

A validation add-on for [nl-to-swmm](https://github.com/Mooly612/nl-to-swmm).
It reads EPA SWMM drainage models (`.json` / `.inp`) and checks the **pipe
parameters** against the Chinese standard **GB 50014-2021 «室外排水设计标准»**
(*Standard for design of outdoor wastewater engineering*).

It reports each violation with a short description, the **exact clause**, a quote
of the requirement, and a concrete fix — or a success message if the model is
compliant. A local web GUI runs on `localhost`; a terminal mode is also provided.

---

## How it works (in one picture)

```
 SWMM model (.json / .inp)
        │
        ▼
 parsers.py    read pipes & nodes; diameter → mm; slope computed from node inverts
        │
        ▼
 hydraulics.py velocity (Manning), fill ratio
        │
        ▼
 rules.py      compare against thresholds from standards/gb50014.json
        │       → Finding(clause, actual, required)
        ▼
 llm_review.py format the report
        │       • locally (templates + real clause quotes), OR
        │       • via Claude API (wording only — never the numbers)
        ▼
 app.py / cli.py  show result (browser or terminal)
```

**All the maths and every comparison happen locally in Python.** The Claude API
is optional and only *rephrases* the already-computed findings — it never does
arithmetic and never "reads the standard from the internet". The thresholds and
clause numbers live in one local file, `swmm_compliance/standards/gb50014.json`.

| Stage | Works offline? | Needs API key? |
|---|:---:|:---:|
| Parse model, compute slope/velocity, find violations | ✅ | ❌ |
| Local report (clause quote + recommendation) | ✅ | ❌ |
| Detailed Claude report (nicer wording) | ❌ | ✅ |

> Without a key the tool is fully functional — you just get the local report.

---

## Requirements

- **Python 3.10–3.13** (3.14 has a known broken build on some macOS Homebrew
  setups — see [Troubleshooting](docs/TROUBLESHOOTING.md)).
- No SWMM install needed to run the checks.

## Install & run

### macOS / Linux

```bash
git clone <your-repo-url> swmm-compliance && cd swmm-compliance
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m streamlit run swmm_compliance/app.py
```

### Windows (PowerShell)

```powershell
git clone <your-repo-url> swmm-compliance ; cd swmm-compliance
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m streamlit run swmm_compliance/app.py
```

The GUI opens automatically at **http://localhost:8501**.

### Optional: short command

```bash
.venv/bin/pip install -e .      # Windows: .venv\Scripts\pip install -e .
swmm-compliance                 # launches the GUI
swmm-compliance check model.json stormwater   # terminal check, prints JSON
```

### Enabling the Claude report (optional)

Create a `.env` file with your Anthropic API key — full instructions in
[docs/CONFIGURATION.md](docs/CONFIGURATION.md):

```bash
cp .env.example .env      # then edit .env and paste your key
```

---

## Input: what to feed it

Upload **one file** (`.json` or `.inp`) in the GUI, or pass a path in the CLI.

- **`.json`** — the nl-to-swmm schema (`conduits`, `junctions`, `outfalls`, …).
- **`.inp`** — EPA SWMM input file (`[CONDUITS]`, `[XSECTIONS]`, `[JUNCTIONS]`,
  `[OUTFALLS]`).

**Diameter is read in metres** (`geom1_diameter_or_height_m`) and converted to mm.
**Slope is not read — it is computed** from node invert elevations, pipe offsets
and length. Full field-by-field reference: [docs/INPUT_FORMATS.md](docs/INPUT_FORMATS.md).

Minimal `.json` example:

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

## Output: what to expect

For every pipe the checker reports, per parameter:

- **Violation** — plain description (e.g. `DN150 < min DN300`);
- **Clause** — exact reference, e.g. `GB 50014-2021 §4.2.3`;
- **Quote** — the requirement text from the local snapshot;
- **Recommendation** — a concrete engineering fix.

If nothing is wrong: **“No violations found. Check passed.”**

### Network class matters

Thresholds differ by network type — pick the right one (`stormwater`, `sewage`,
`combined`, `inlet_connection`). See the ❔ tooltip in the GUI or
[docs/STANDARDS.md](docs/STANDARDS.md).

### Checked parameters

| Parameter | Source | Clause* |
|---|---|---|
| Min diameter 最小管径 | model | §4.2.3 |
| Min slope 最小设计坡度 | computed from node inverts | §4.2.3 |
| Velocity (min/max) 设计流速 | Manning | §4.2.4 / §4.2.5 |
| Fill ratio h/D 设计充满度 | needs simulation output | §4.2.1 |

\* Clause numbers are flagged `verify_against_official` in the snapshot — confirm
against the official PDF. See [docs/STANDARDS.md](docs/STANDARDS.md).

---

## Documentation

- **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** — API key, `.env`, server
  port, cache, all tunables.
- **[docs/STANDARDS.md](docs/STANDARDS.md)** — how the standard is stored and
  **how to update it when the norm changes** (edit one JSON file).
- **[docs/INPUT_FORMATS.md](docs/INPUT_FORMATS.md)** — full field reference for
  `.json` and `.inp`.
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** — common errors and fixes.

## Project layout

```
swmm_compliance/
├── standards/gb50014.json   # local snapshot: thresholds + clause references
├── parsers.py               # read .json (nl-to-swmm) and .inp (SWMM)
├── hydraulics.py            # slope, velocity (Manning), fill ratio
├── rules.py                 # deterministic rule engine → Finding
├── llm_review.py            # Claude API layer + on-disk report cache
├── checker.py               # orchestration
├── app.py                   # Streamlit GUI
└── cli.py                   # entry point: GUI or terminal check
```

## Security

Secrets never enter git: `.env`, `.cache/`, `.venv/`, `*.key` and
`.streamlit/secrets.toml` are in `.gitignore`. Only `.env.example` (a placeholder)
is committed. **Never paste your API key anywhere but your local `.env`.**
