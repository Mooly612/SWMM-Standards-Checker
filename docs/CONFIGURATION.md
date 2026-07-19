# Configuration

Everything you can tune, and where.

---

## 1. Anthropic API key (optional)

The Claude report is optional. Without a key the tool still finds every
violation and produces a **local report** — you only lose the nicer Claude
wording.

### Where the key goes

A file named exactly **`.env`** in the project root:

```
ANTHROPIC_API_KEY=sk-ant-api03-XXXXXXXX...
```

Rules that trip people up:

- filename is **`.env`**, not `.env.txt`, not `.env.example`;
- **no spaces** around `=`;
- **no quotes** around the key.

### Create it

**macOS / Linux**
```bash
cp .env.example .env
# then open .env in an editor and paste your key
# or in one line:
echo 'ANTHROPIC_API_KEY=sk-ant-api03-XXXX' > .env
```

**Windows (PowerShell)**
```powershell
Copy-Item .env.example .env
# edit .env, or:
Set-Content .env 'ANTHROPIC_API_KEY=sk-ant-api03-XXXX'
```

Get a key at <https://console.anthropic.com/settings/keys>.

### Verify it is picked up

Restart the app. The left panel shows **🟢 ANTHROPIC_API_KEY detected** and the
“Detailed report via Claude” toggle becomes active.

### Replace / rotate the key

1. Revoke the old key in the [Anthropic console](https://console.anthropic.com/settings/keys).
2. Create a new one.
3. Overwrite the line in `.env` (same command as above).
4. Restart the app.


### Which model is used

`claude-opus-4-8`, set in `swmm_compliance/llm_review.py` (constant `MODEL`).
Change that one line to use another model.

---

## 2. Report cache

Claude reports are cached on disk at **`.cache/llm_reports.json`**, keyed by the
computed numbers + network class + model. Identical inputs never hit the API
twice. There is also an in-session cache so toggling options is instant.

**Clear the cache** (e.g. after editing recommendation text and wanting a fresh
Claude answer):

```bash
rm -f .cache/llm_reports.json          # macOS/Linux
Remove-Item .cache\llm_reports.json    # Windows PowerShell
```

The `.cache/` folder is git-ignored.

---

## 3. Streamlit server

Config lives in `.streamlit/config.toml`.

- **Port** — default `8501`. Change per run:
  ```bash
  .venv/bin/python -m streamlit run swmm_compliance/app.py --server.port 8600
  ```
- **Toolbar / “Deploy” button** — hidden via `toolbarMode = "minimal"`.
- **Usage stats** — disabled (`gatherUsageStats = false`).

---

## 4. Network class

Passed in the GUI dropdown, or as the 2nd CLI argument:

```bash
swmm-compliance check model.inp sewage
```

Valid values: `stormwater`, `sewage`, `combined`, `inlet_connection`.
They select different thresholds — see [STANDARDS.md](STANDARDS.md).

---

## 5. CLI flags

```bash
swmm-compliance                         # launch GUI
swmm-compliance check <file> [class]    # terminal check → JSON to stdout
swmm-compliance check <file> --no-llm   # force local report (skip Claude)
```

Exit code of `check`: `0` if compliant, `1` if violations found.
