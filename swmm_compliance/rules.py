"""Deterministic GB 50014-2021 rule engine.

Design principle
----------------
All numeric comparison is done HERE in Python against the local snapshot
(standards/gb50014.json). We never ask the LLM to do arithmetic it can get
wrong, and clause citations come straight from the JSON — a single, editable
source of truth. The LLM layer (llm_review.py) only turns these structured
findings into readable prose and suggestions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal, Optional

from .hydraulics import full_flow_velocity_mps, infer_material, is_plastic
from .parsers import Model, Pipe

STANDARDS_PATH = Path(__file__).parent / "standards" / "gb50014.json"

Severity = Literal["violation", "warning", "info"]
PipeClass = Literal["sewage", "stormwater", "combined", "inlet_connection"]


@dataclass
class Finding:
    pipe: str
    parameter: str
    severity: Severity
    message: str          # short human description of the issue
    clause: str           # e.g. "GB 50014-2021 §4.2.3"
    actual: Optional[float] = None
    required: Optional[float] = None
    unit: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def load_standard(path: str | Path = STANDARDS_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _clause(std: dict, rule_key: str) -> str:
    code = std["standard"]["code"]
    c = std["rules"][rule_key].get("clause", "?")
    return f"{code} §{c}"


class ComplianceEngine:
    def __init__(self, standard: Optional[dict] = None):
        self.std = standard or load_standard()

    # -- individual checks -------------------------------------------------- #
    def check_diameter(self, p: Pipe, cls: PipeClass) -> Optional[Finding]:
        rule = self.std["rules"]["min_diameter"]
        min_mm = rule["by_class"][cls]["min_mm"]
        if p.diameter_mm > 0 and p.diameter_mm < min_mm - 1e-6:
            return Finding(
                pipe=p.name, parameter="diameter", severity="violation",
                message=(f"管径 DN{p.diameter_mm:.0f} 小于{cls}类管道最小管径 DN{min_mm}"),
                clause=_clause(self.std, "min_diameter"),
                actual=round(p.diameter_mm, 1), required=min_mm, unit="mm",
            )
        return None

    def check_slope(self, p: Pipe, cls: PipeClass) -> Optional[Finding]:
        rule = self.std["rules"]["min_slope"]
        by = rule["by_class"][cls]
        min_slope = by["plastic"] if is_plastic(p.roughness_n) else by["other"]
        s = p.slope
        if s is None:
            return Finding(
                pipe=p.name, parameter="slope", severity="info",
                message="无法根据节点标高推算坡度（缺少 from/to 节点管底标高）",
                clause=_clause(self.std, "min_slope"),
            )
        if s < min_slope - 1e-9:
            return Finding(
                pipe=p.name, parameter="slope", severity="violation",
                message=(f"设计坡度 {s:.4f} 小于最小设计坡度 {min_slope:.4f}"),
                clause=_clause(self.std, "min_slope"),
                actual=round(s, 5), required=min_slope, unit="m/m",
            )
        if s < 0:
            return Finding(
                pipe=p.name, parameter="slope", severity="warning",
                message=f"坡度为负 ({s:.4f})：管道逆坡，需核对节点标高",
                clause=_clause(self.std, "min_slope"),
                actual=round(s, 5), required=min_slope, unit="m/m",
            )
        return None

    def check_velocity(self, p: Pipe, cls: PipeClass) -> list[Finding]:
        out: list[Finding] = []
        mn = self.std["rules"]["min_velocity"]["by_class"].get(cls)
        mx = self.std["rules"]["max_velocity"]["by_material"]

        # prefer simulated velocity; otherwise full-flow Manning proxy
        v = p.sim_velocity_mps
        proxy = v is None
        if proxy:
            v = full_flow_velocity_mps(p.diameter_mm, p.slope or 0.0, p.roughness_n)
        if v is None:
            return out

        note = "（满流 Manning 估算，建议以 SWMM 模拟流速复核）" if proxy else ""
        if mn and v < mn["min_mps"] - 1e-9:
            out.append(Finding(
                pipe=p.name, parameter="velocity_min", severity="warning" if proxy else "violation",
                message=f"流速 {v:.2f} m/s 低于最小设计流速 {mn['min_mps']} m/s{note}",
                clause=_clause(self.std, "min_velocity"),
                actual=round(v, 3), required=mn["min_mps"], unit="m/s",
            ))
        material = infer_material(p.roughness_n)
        cap = mx[material]["max_mps"]
        if v > cap + 1e-9:
            out.append(Finding(
                pipe=p.name, parameter="velocity_max", severity="warning" if proxy else "violation",
                message=f"流速 {v:.2f} m/s 超过{material}管最大设计流速 {cap} m/s{note}",
                clause=_clause(self.std, "max_velocity"),
                actual=round(v, 3), required=cap, unit="m/s",
            ))
        return out

    def check_fill_ratio(self, p: Pipe, cls: PipeClass) -> Optional[Finding]:
        if cls != "sewage":
            return None  # storm/combined designed as full flow
        if p.sim_max_depth_m is None or p.diameter_mm <= 0:
            return None  # requires simulation depth output
        fill = p.sim_max_depth_m / (p.diameter_mm / 1000.0)
        for band in self.std["rules"]["design_fill_ratio"]["table_by_diameter"]:
            if band["d_min_mm"] <= p.diameter_mm <= band["d_max_mm"]:
                if fill > band["max_fill"] + 1e-6:
                    return Finding(
                        pipe=p.name, parameter="fill_ratio", severity="violation",
                        message=f"设计充满度 h/D={fill:.2f} 超过上限 {band['max_fill']}",
                        clause=_clause(self.std, "design_fill_ratio"),
                        actual=round(fill, 3), required=band["max_fill"], unit="h/D",
                    )
        return None

    # -- orchestration ------------------------------------------------------ #
    def check_pipe(self, p: Pipe, cls: PipeClass) -> list[Finding]:
        findings: list[Finding] = []
        for f in (self.check_diameter(p, cls), self.check_slope(p, cls),
                  self.check_fill_ratio(p, cls)):
            if f:
                findings.append(f)
        findings.extend(self.check_velocity(p, cls))
        return findings

    def check_model(self, model: Model, pipe_class: PipeClass = "stormwater") -> list[Finding]:
        findings: list[Finding] = []
        for p in model.pipes:
            findings.extend(self.check_pipe(p, pipe_class))
        return findings
