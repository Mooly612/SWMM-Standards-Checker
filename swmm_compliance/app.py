"""Streamlit GUI for the GB 50014-2021 compliance checker.

Launch cross-platform from a terminal with:  swmm-compliance
(or:  python -m streamlit run swmm_compliance/app.py)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from swmm_compliance.checker import check_model
from swmm_compliance.parsers import load_inp_model, load_json_model


def _load_dotenv() -> None:
    """Read .env from the project root so ANTHROPIC_API_KEY reaches the environment."""
    for base in (Path.cwd(), Path(__file__).resolve().parent.parent):
        f = base / ".env"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


_load_dotenv()

st.set_page_config(page_title="SWMM · GB 50014 Compliance", page_icon="🛠️",
                   layout="wide", menu_items={})

# Strip default Streamlit chrome + keep the upload widget narrow.
st.markdown("""
<style>
[data-testid="stHeaderActionElements"] {display: none !important;}   /* anchor icons on headings */
[data-testid="stToolbar"] {display: none !important;}                /* top-right toolbar */
[data-testid="stStatusWidget"] {display: none !important;}           /* Running / status */
[data-testid="stDecoration"] {display: none !important;}
footer {visibility: hidden !important; height: 0 !important;}         /* Made with Streamlit */
[data-testid="stFileUploader"] {max-width: 560px;}                   /* keep uploader compact */
[data-testid="stWidgetLabel"] {width: fit-content;}                  /* ❔ help icon hugs the label text */
</style>
""", unsafe_allow_html=True)

st.title("SWMM Compliance Checker (in accordance with GB 50014-2021)")
st.caption("Checks pipe parameters (diameter, slope, velocity) against the Chinese standard "
           "«室外排水设计标准». Violations are found by local computation; Claude only "
           "phrases the explanation and recommendations.")

CLASS_HELP = (
    "GB 50014-2021 sets **different thresholds** per network type — pick the right class:\n\n"
    "- **污水管 · Sewage** — foul / industrial wastewater only. Partial-fill design; "
    "min velocity 0.6 m/s; a fill-ratio (h/D) limit applies.\n"
    "- **雨水管 · Stormwater** — rainwater runoff only. Full-bore flow; min velocity 0.75 m/s.\n"
    "- **合流管 · Combined** — sewage + stormwater together. Like stormwater; min velocity 0.75 m/s.\n"
    "- **雨水口连接管 · Inlet connection** — short pipe from a gully to the manhole. "
    "Min diameter DN200, slope 0.01."
)

col_cfg, col_main = st.columns([1, 3])

with col_cfg:
    pipe_class = st.selectbox(
        "Network class (管道类别)",
        options=["stormwater", "sewage", "combined", "inlet_connection"],
        format_func=lambda x: {
            "stormwater": "雨水管 · Stormwater",
            "sewage": "污水管 · Sewage",
            "combined": "合流管 · Combined",
            "inlet_connection": "雨水口连接管 · Inlet connection",
        }[x],
        help=CLASS_HELP,  # the ❔ icon sits right next to the label
    )

    _has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    use_llm = st.toggle(
        "Detailed report via Claude", value=_has_key, disabled=not _has_key,
        help="Claude quotes the exact standard clause and gives a fuller recommendation. "
             "Off / no key → local report (same violations and clauses, shorter wording).",
    )
    st.caption("🟢 ANTHROPIC_API_KEY detected" if _has_key
               else "⚪️ No key → local report. Add it to the `.env` file")

with col_main:
    up = st.file_uploader("Upload a SWMM model (one file)", type=["json", "inp"], key="uploader")
    demo = st.checkbox("Load demo example (DN & slope violation)", key="demo")

# ---- Model selection: the DEMO toggle wins while it is on; uncheck it → the
#      uploaded file is shown. So: file → shows file; tick demo → demo; untick → file. ----
model = None
if demo:
    model = load_json_model({
        "title": "Demo — DN150 @ 0.001 (violates DN300 / 0.002-0.003)",
        "junctions": [{"name": "J1", "invert_elevation_m": 100.0, "max_depth_m": 2.0}],
        "outfalls": [{"name": "O1", "invert_elevation_m": 99.82}],
        "conduits": [{"name": "C1", "from_node": "J1", "to_node": "O1",
                      "length_m": 180, "geom1_diameter_or_height_m": 0.15,
                      "roughness_manning_n": 0.013}],
    })
elif up is not None:
    raw = up.read().decode("utf-8", errors="ignore")
    try:
        if up.name.lower().endswith(".json"):
            model = load_json_model(json.loads(raw))
        else:
            import os as _os
            import tempfile
            with tempfile.NamedTemporaryFile("w", suffix=".inp", delete=False, encoding="utf-8") as tmp:
                tmp.write(raw)
                tmp_path = tmp.name
            model = load_inp_model(tmp_path)
            _os.unlink(tmp_path)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not parse file: {e}")

def _model_sig(m) -> str:
    """Stable signature of a model → identical inputs reuse the stored result."""
    return json.dumps({"t": m.title, "p": [vars(p) for p in m.pipes]},
                      sort_keys=True, default=str)


if model is not None:
    # In-session cache: toggling Claude / demo back to a state already computed
    # returns instantly — no spinner, no re-run, no API call.
    sig = (_model_sig(model), pipe_class, use_llm)
    _cache = st.session_state.setdefault("_result_cache", {})
    if sig in _cache:
        result = _cache[sig]
    else:
        with st.spinner("Checking against GB 50014-2021…", show_time=True):
            result = check_model(model, pipe_class=pipe_class, use_llm=use_llm)
        _cache[sig] = result
    report = result["report"]

    st.divider()
    st.subheader(f"Model: {result['title']}  ·  pipes: {result['pipe_count']}")

    if report and report["status"] == "passed":
        st.success("✅ " + report["summary"])
    elif report:
        st.error(f"❌ {report['summary']}")
        for i, issue in enumerate(report["issues"], 1):
            with st.expander(f"{i}. {issue['pipe']} — {issue['parameter']}", expanded=True):
                st.markdown(f"**Violation:** {issue['description']}")
                st.markdown(f"**Standard clause:** `{issue['clause']}`")
                st.markdown(f"> {issue['clause_quote']}")
                st.markdown(f"**Recommendation:** {issue['recommendation']}")

    if result["findings"]:
        with st.expander("Violations table (parameter · actual · required)"):
            st.dataframe(
                [
                    {
                        "Pipe": f["pipe"],
                        "Parameter": f["parameter"],
                        "Actual": f"{f.get('actual', '')} {f.get('unit', '')}".strip(),
                        "Required": f"{f.get('required', '')} {f.get('unit', '')}".strip(),
                        "Clause": f["clause"],
                    }
                    for f in result["findings"]
                ],
                use_container_width=True, hide_index=True,
            )
