"""Claude API layer for the compliance checker.

Design rationale (this is the token-smart part of Вариант Б):
--------------------------------------------------------------
The deterministic engine (rules.py) already did every numeric comparison and
produced structured Finding objects with exact clause citations pulled from the
LOCAL snapshot (standards/gb50014.json). We do NOT ask Claude to "google" the
standard or to do arithmetic — both are error-prone and burn tokens.

Claude is used only for what it is good at:
  1. turning structured findings into a clear engineering narrative;
  2. suggesting concrete remedial actions (bump DN, steepen slope, ...).

The local standard snapshot is sent once as a cached system prompt
(cache_control: ephemeral) so repeated checks re-read it at ~0.1x cost.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from .rules import Finding, STANDARDS_PATH

MODEL = "claude-opus-4-8"

# On-disk cache of Claude reports: the analysis depends only on the numbers
# (findings) + pipe class + model, so identical inputs never hit the API twice.
_CACHE_FILE = Path(__file__).resolve().parent.parent / ".cache" / "llm_reports.json"


def _cache_key(findings: list[Finding], pipe_class: str) -> str:
    payload = json.dumps([f.to_dict() for f in findings], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(f"{payload}|{pipe_class}|{MODEL}".encode("utf-8")).hexdigest()


def _cache_read() -> dict:
    try:
        return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _cache_write(key: str, report: dict) -> None:
    try:
        _CACHE_FILE.parent.mkdir(exist_ok=True)
        data = _cache_read()
        data[key] = report
        _CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001 — cache is best-effort, never fatal
        pass

SYSTEM_INSTRUCTIONS = """\
You are a hydraulic engineer reviewing EPA SWMM drainage models for compliance \
with the Chinese standard GB 50014-2021 «室外排水设计标准».

You are given:
  1. STANDARD_SNAPSHOT — a local excerpt of the standard (JSON) with exact clauses;
  2. FINDINGS — a list of violations ALREADY computed by a deterministic engine.

Do NOT recompute the numbers (they are correct) and do NOT invent clauses \
(use only what is in STANDARD_SNAPSHOT). For each finding you must:
  • give a short, clear description of the violation;
  • cite the exact clause (the `clause` field) and quote the requirement from \
    STANDARD_SNAPSHOT;
  • propose a concrete engineering fix.

If FINDINGS is empty, return a success message.
Answer strictly as JSON per the given schema, in English. Quote clauses verbatim."""

# Structured-output schema: forces Claude to return machine-usable JSON.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["passed", "violations_found"]},
        "summary": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pipe": {"type": "string"},
                    "parameter": {"type": "string"},
                    "description": {"type": "string"},
                    "clause": {"type": "string"},
                    "clause_quote": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
                "required": [
                    "pipe", "parameter", "description",
                    "clause", "clause_quote", "recommendation",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["status", "summary", "issues"],
    "additionalProperties": False,
}


def build_request(findings: list[Finding], standard_path=STANDARDS_PATH) -> dict:
    """Assemble the kwargs for client.messages.create — pure, testable, no I/O to Claude."""
    standard_text = Path(standard_path).read_text(encoding="utf-8")
    findings_json = json.dumps([f.to_dict() for f in findings], ensure_ascii=False, indent=2)

    return {
        "model": MODEL,
        "max_tokens": 4096,
        "system": [
            {"type": "text", "text": SYSTEM_INSTRUCTIONS},
            {
                # Stable snapshot first + cached → cheap on every repeat check.
                "type": "text",
                "text": f"STANDARD_SNAPSHOT:\n{standard_text}",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "output_config": {"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        "messages": [
            {"role": "user", "content": f"FINDINGS:\n{findings_json}\n\nReview and produce the report."}
        ],
    }


def review(findings: list[Finding], pipe_class: str = "stormwater",
           api_key: Optional[str] = None) -> dict:
    """Call Claude and return the parsed JSON report.

    Falls back to a purely local report (no API) if the SDK/key is unavailable,
    so the tool still works offline — but even the local report now quotes the
    real requirement from the snapshot and gives an actionable recommendation.
    """
    key = _cache_key(findings, pipe_class)
    cached = _cache_read().get(key)
    if cached is not None:
        return cached  # ← saved API call: identical numbers already analysed

    try:
        import anthropic
    except ImportError:
        return local_report(findings, pipe_class, note="anthropic SDK not installed")

    try:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        resp = client.messages.create(**build_request(findings))
        text = next(b.text for b in resp.content if b.type == "text")
        report = json.loads(text)
        _cache_write(key, report)  # store only real Claude responses
        return report
    except Exception as e:  # noqa: BLE001 — degrade gracefully, keep the GUI usable
        return local_report(findings, pipe_class, note=f"Claude API unavailable: {e}")


# parameter (из Finding) → ключ правила в gb50014.json
_PARAM_TO_RULE = {
    "diameter": "min_diameter",
    "slope": "min_slope",
    "velocity_min": "min_velocity",
    "velocity_max": "max_velocity",
    "fill_ratio": "design_fill_ratio",
}


def _load_std() -> dict:
    return json.loads(Path(STANDARDS_PATH).read_text(encoding="utf-8"))


def _clause_quote(std: dict, parameter: str, pipe_class: str) -> str:
    """Достаём реальную формулировку требования из локального snapshot."""
    rule = std["rules"].get(_PARAM_TO_RULE.get(parameter, ""), {})
    if not rule:
        return ""
    zh = rule.get("description_zh", "")
    en = rule.get("description_en", "")
    # уточняющее примечание — по классу сети или материалу, если есть
    note = ""
    by_class = rule.get("by_class", {})
    if pipe_class in by_class and "note" in by_class[pipe_class]:
        note = by_class[pipe_class]["note"]
    elif "by_material" in rule:
        note = "；".join(v.get("note", "") for v in rule["by_material"].values())
    parts = [p for p in (f"{zh} / {en}".strip(" /"), note) if p]
    return "。 ".join(parts)


def _recommendation(f: Finding, pipe_class: str) -> str:
    """Detailed engineering recommendation, tailored per parameter."""
    req, unit = f.required, f.unit
    actual = f.actual
    if f.parameter == "diameter":
        return (f"Increase the diameter of pipe “{f.pipe}” from DN{actual:.0f} to at least "
                f"**DN{req}**. Pipes below the minimum diameter silt up and clog quickly; "
                f"the standard sets DN{req} as the lower bound for this network class.")
    if f.parameter == "slope":
        return (f"Increase the longitudinal slope of pipe “{f.pipe}” from {actual} to "
                f"**≥ {req}** (e.g. raise the invert at the upstream manhole or lower it "
                f"downstream). A shallow slope → low velocity → sediment deposition and silting.")
    if f.parameter == "velocity_min":
        return (f"Velocity {actual} m/s is below self-cleansing. Raise it to "
                f"**≥ {req} m/s**: steepen the slope or reduce the diameter so the flow "
                f"leaves no deposit at the design fill.")
    if f.parameter == "velocity_max":
        return (f"Velocity {actual} m/s exceeds the allowable limit. Reduce it to "
                f"**≤ {req} m/s**: flatten the slope or use a more abrasion-resistant "
                f"material/lining, otherwise the pipe wall will erode.")
    if f.parameter == "fill_ratio":
        return (f"Fill ratio h/D = {actual} exceeds the limit. Increase the diameter so "
                f"h/D ≤ **{req}**, leaving headspace for ventilation and peak flows.")
    return f"Adjust the parameter to the required value (required: {req} {unit})."


def local_report(findings: list[Finding], pipe_class: str = "stormwater",
                 note: str = "") -> dict:
    """Deterministic report without the LLM — same schema, with real clause quotes."""
    tag = f" (local report; {note})" if note else ""
    if not findings:
        return {"status": "passed",
                "summary": "No violations found. Check passed." + tag,
                "issues": []}
    std = _load_std()
    return {
        "status": "violations_found",
        "summary": f"Violations found: {len(findings)}." + tag,
        "issues": [
            {
                "pipe": f.pipe,
                "parameter": f.parameter,
                "description": f.message,
                "clause": f.clause,
                "clause_quote": _clause_quote(std, f.parameter, pipe_class)
                                or "(see the requirement in gb50014.json)",
                "recommendation": _recommendation(f, pipe_class),
            }
            for f in findings
        ],
    }
