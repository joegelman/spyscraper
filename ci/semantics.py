# ci/semantics.py
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Optional
import json


@dataclass
class EvidenceItem:
    url: str
    quote: str
    score: float | None = None


@dataclass
class ProofPoint:
    claim: str
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass
class Capability:
    name: str
    description: str = ""
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass
class Module:
    name: str
    one_liner: str
    description: str
    key_capabilities: list[Capability] = field(default_factory=list)
    proof_points: list[ProofPoint] = field(default_factory=list)
    target_buyers: list[str] = field(default_factory=list)
    integrations: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)


@dataclass
class OfferingSemantics:
    vendor: str
    domain: str

    # positioning snapshot
    positioning_one_liner: str
    category: list[str] = field(default_factory=list)
    target_segments: list[str] = field(default_factory=list)
    differentiators: list[str] = field(default_factory=list)

    # product structure
    modules: list[Module] = field(default_factory=list)

    # meta
    notable_claims: list[ProofPoint] = field(default_factory=list)
    deemphasized_or_missing: list[str] = field(default_factory=list)
    risks_or_ambiguities: list[str] = field(default_factory=list)

    # traceability
    evidence_urls_used: list[str] = field(default_factory=list)


def to_json(obj: Any, path: str, indent: int = 2) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(obj), f, ensure_ascii=False, indent=indent)


def from_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_semantics(d: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Lightweight validation to keep this stdlib-only.
    Returns (ok, errors).
    """
    errors: list[str] = []
    for k in ["vendor", "domain", "positioning_one_liner", "modules"]:
        if k not in d:
            errors.append(f"missing field: {k}")

    if "modules" in d and not isinstance(d["modules"], list):
        errors.append("modules must be a list")

    # minimal module checks
    for i, m in enumerate(d.get("modules", [])):
        if not isinstance(m, dict):
            errors.append(f"modules[{i}] must be an object")
            continue
        for k in ["name", "one_liner", "description"]:
            if k not in m:
                errors.append(f"modules[{i}] missing field: {k}")

    return (len(errors) == 0, errors)

