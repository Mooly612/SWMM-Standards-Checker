# Troubleshooting

### `zsh: command not found: from` (or similar)

You pasted **Python code** into the terminal. Don’t run the code lines by hand —
run the launch command:

```bash
.venv/bin/python -m streamlit run swmm_compliance/app.py
```

---

### `ModuleNotFoundError: No module named 'streamlit'`

Dependencies aren’t installed, or you’re using the wrong Python. Install into the
project venv:

```bash
.venv/bin/pip install -r requirements.txt      # macOS/Linux
.venv\Scripts\pip install -r requirements.txt  # Windows
```

---

### `pip` itself crashes with `pyexpat` / `libexpat` symbol error (macOS)

Your `python3` is a **broken Homebrew Python 3.14** build. Use a working version
(3.13/3.12/3.11) for the venv:

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Optionally fix the default:

```bash
brew reinstall python@3.14
# or switch default to a working one:
brew unlink python@3.14 && brew link --overwrite python@3.13
```

---

### “Claude API unavailable” even though I have a key

- The key must be in a file named exactly **`.env`** (not `.env.example`), with
  **no spaces** around `=` and **no quotes**. See
  [CONFIGURATION.md](CONFIGURATION.md).
- **Restart** the app after creating `.env` — it is read at startup.
- Check the left panel: it should say **🟢 ANTHROPIC_API_KEY detected**.

---

### Code changes don’t take effect / old behaviour persists

Streamlit hot-reloads `app.py` but **not** imported modules
(`checker.py`, `llm_review.py`, …). Do a **full restart**: press **Ctrl+C** in
the terminal, then relaunch. In the browser, hard-refresh with
**Cmd/Ctrl + Shift + R**.

---

### The report shows stale or wrong text (e.g. a leftover value)

Clear the on-disk report cache and restart:

```bash
rm -f .cache/llm_reports.json          # macOS/Linux
Remove-Item .cache\llm_reports.json    # Windows
```

---

### “No violations found” never appears without Claude

Fixed — the report is now produced in both modes. If you still see it, you’re
running stale modules: do a **full restart** (above).

---

### Port 8501 already in use

```bash
.venv/bin/python -m streamlit run swmm_compliance/app.py --server.port 8600
```

---

### The uploaded file won’t parse

- Make sure it’s a valid nl-to-swmm `.json` or an EPA SWMM `.inp`.
- `from_node` / `to_node` on each conduit must match a junction/outfall name,
  otherwise slope can’t be computed. See [INPUT_FORMATS.md](INPUT_FORMATS.md).
