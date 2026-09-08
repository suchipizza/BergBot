"""Register controller (FR-R1/R2). Rule-based, never model mood."""

from __future__ import annotations

from bergbot.core.domain import (
    SERIOUS_WARNING_TYPES,
    Audit,
    Intent,
    QuestionKind,
    Register,
    RegisterDecision,
    Severity,
)


def decide(
    audit: Audit | None, intent: Intent, question: QuestionKind = QuestionKind.none
) -> RegisterDecision:
    """serious if: any warning severity in {critical, important}; any warning type in
    {closure, fire_restriction, shooting_activity, avalanche_context, exposed_wind};
    question is safety; intent is emergency. Otherwise playful."""
    reasons: list[str] = []
    severity: Severity | None = None
    if intent is Intent.emergency:
        reasons.append("intent:emergency")
    if question is QuestionKind.safety:
        reasons.append("question:safety")
    if audit is not None:
        severity = audit.max_severity
        for w in audit.warnings:
            if w.severity in (Severity.critical, Severity.important):
                reasons.append(f"severity:{w.severity.value}:{w.type.value}")
            if w.type in SERIOUS_WARNING_TYPES:
                reasons.append(f"type:{w.type.value}")
    serious = bool(reasons)
    return RegisterDecision(
        mode=Register.serious if serious else Register.playful,
        reasons=sorted(set(reasons)),
        mascot_allowed=not serious,
        media_offer_allowed=not serious,
        emoji_allowed=not serious,
        severity=severity,
    )
