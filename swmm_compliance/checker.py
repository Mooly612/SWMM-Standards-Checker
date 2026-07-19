"""Top-level orchestration: parse a model, run rules, optionally get an LLM report."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from .llm_review import review, local_report
from .parsers import Model, load_any, load_json_model
from .rules import ComplianceEngine, Finding

PipeClass = Literal["sewage", "stormwater", "combined", "inlet_connection"]


def check_file(path: str | Path, pipe_class: PipeClass = "stormwater",
               use_llm: bool = True) -> dict:
    model = load_any(path)
    return check_model(model, pipe_class, use_llm)


def check_model(model: Model, pipe_class: PipeClass = "stormwater",
                use_llm: bool = True) -> dict:
    findings: list[Finding] = ComplianceEngine().check_model(model, pipe_class)
    # Report is ALWAYS produced: Claude when enabled (falls back to local on error),
    # pure local otherwise — so the pass/fail message shows in both modes.
    report = review(findings, pipe_class=pipe_class) if use_llm \
        else local_report(findings, pipe_class)
    return {
        "title": model.title,
        "source": model.source,
        "pipe_count": len(model.pipes),
        "findings": [f.to_dict() for f in findings],
        "report": report,
    }
