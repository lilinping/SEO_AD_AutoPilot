"""PolicyGuard Agent - Policy compliance and content safety enforcement.

Flags deceptive content, spam signals, thin pages, keyword stuffing,
and other Google Webmaster Guidelines violations before they ship.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import Agent, AgentOutput, AgentRole, DebateOpinion, DebateStance, SiteContext


_DECEPTIVE = [
    "guaranteed results", "guaranteed ranking", "guaranteed #1",
    "100% success", "instant traffic", "secret formula",
    "miracle solution", "never fail", "unlimited clicks",
    "#1 on google", "buy backlinks", "hidden links",
    "cloaking", "doorway pages", "link farm",
]
_SPAM = [
    "keyword stuffing", "invisible text", "hidden text",
    "duplicate content", "scraped content", "auto-generated spam",
]


class PolicyGuardAgent(Agent):
    """PolicyGuard Agent - enforces content policy and ethical-SEO compliance.

    Responsibilities:
    - Detect deceptive / spammy content patterns
    - Flag keyword stuffing and thin content
    - Enforce Google Webmaster Guidelines compliance
    - Risk-score proposals before execution
    """

    def __init__(self):
        super().__init__()
        self._role = AgentRole.POLICY_GUARD

    # ── Public interface ─────────────────────────────────────────────────

    def analyze(self, context: SiteContext) -> AgentOutput:
        """Audit site context for policy violations."""
        raw = context.raw_data or {}
        violations = self._detect_violations(raw)
        risk = self._risk_level(violations)
        score = self._compliance_score(violations)

        return self._create_output(
            content={
                "compliance_score": score,
                "risk_level": risk,
                "violations": violations,
                "recommendations": self._recommendations(violations),
                "policy_summary": self._summary(violations, score),
            },
            confidence=0.90,
            risk_score=round(1.0 - score, 2),
            needs_human_review=risk in ("high", "critical"),
            reasoning=f"{len(violations)} violations; risk={risk}; compliance={score:.0%}",
        )

    def offer_opinion(
        self,
        topic: str,
        proposal: dict[str, Any],
        context: SiteContext,
        previous_opinions: list[DebateOpinion] = None,
    ) -> DebateOpinion:
        """Vote on a proposal from a policy-compliance perspective."""
        violations = self._scan_proposal(proposal)
        critical = [v for v in violations if v["severity"] == "critical"]
        high = [v for v in violations if v["severity"] == "high"]

        if critical:
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.DISAGREE,
                reasoning=f"Critical violations: {', '.join(v['type'] for v in critical)}",
                evidence=[v["detail"] for v in critical],
                confidence=0.95,
                conditions=["Remove all deceptive / prohibited content before proceeding"],
            )
        if high:
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.PARTIALLY_AGREE,
                reasoning=f"High-severity issues: {', '.join(v['type'] for v in high)}",
                evidence=[v["detail"] for v in high],
                confidence=0.80,
                conditions=[f"Fix: {v['type']}" for v in high],
            )
        return DebateOpinion(
            agent_role=self._role,
            stance=DebateStance.AGREE,
            reasoning="Proposal appears policy-compliant; no critical violations detected.",
            evidence=["No deceptive triggers found", "Content volume within acceptable range"],
            confidence=0.85,
        )

    def challenge(self, other_output: AgentOutput, context: SiteContext) -> Optional[dict[str, Any]]:
        """Challenge outputs that contain policy-violating recommendations."""
        content = other_output.content or {}
        blob = (
            str(content.get("strategy", "")) + " "
            + " ".join(str(x) for x in content.get("recommendations", []))
        ).lower()
        hits = [t for t in _DECEPTIVE + _SPAM if t in blob]
        if not hits:
            return None
        return {
            "type": "policy_violation",
            "challenger": self._role.value,
            "violated_guidelines": hits,
            "severity": "high",
            "recommendation": "Remove / rephrase content violating Google Webmaster Guidelines",
        }

    # ── Private helpers ──────────────────────────────────────────────────

    def _detect_violations(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        combined = (str(raw.get("content", "")) + " " + str(raw.get("meta", ""))).lower()
        words = combined.split()
        wc = len(words)

        for t in _DECEPTIVE:
            if t in combined:
                out.append({"type": "deceptive_content", "severity": "critical",
                             "detail": f"Deceptive phrase: '{t}'"})
        for t in _SPAM:
            if t in combined:
                out.append({"type": "spam_signal", "severity": "high",
                             "detail": f"Spam pattern: '{t}'"})
        if 0 < wc < 300:
            out.append({"type": "thin_content", "severity": "medium",
                         "detail": f"Content too thin: {wc} words (min 300)"})
        for kw in raw.get("target_keywords", []):
            density = combined.count(kw.lower()) / max(wc, 1)
            if density > 0.05:
                out.append({"type": "keyword_stuffing", "severity": "high",
                             "detail": f"'{kw}' density {density:.1%} > 5% threshold"})
        return out

    def _scan_proposal(self, proposal: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        text = str(proposal).lower()
        for t in _DECEPTIVE:
            if t in text:
                out.append({"type": "deceptive_proposal", "severity": "critical",
                             "detail": f"Prohibited phrase in proposal: '{t}'"})
        for t in _SPAM:
            if t in text:
                out.append({"type": "spam_proposal", "severity": "high",
                             "detail": f"Spam technique in proposal: '{t}'"})
        return out

    def _risk_level(self, violations: list[dict[str, Any]]) -> str:
        sevs = {v["severity"] for v in violations}
        for s in ("critical", "high", "medium"):
            if s in sevs: return s
        return "low"

    def _compliance_score(self, violations: list[dict[str, Any]]) -> float:
        penalty = {"critical": 0.30, "high": 0.15, "medium": 0.05}
        return max(0.0, 1.0 - sum(penalty.get(v["severity"], 0.0) for v in violations))

    def _recommendations(self, violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        actions = {
            "deceptive_content": "Remove / rewrite deceptive claims with accurate, verifiable benefits.",
            "spam_signal": "Eliminate spam techniques; replace with white-hat alternatives.",
            "thin_content": "Expand content to >= 600 words with meaningful, user-centric information.",
            "keyword_stuffing": "Reduce keyword density; aim for <= 2% and natural usage.",
            "deceptive_proposal": "Revise proposal to remove unsubstantiated guarantees.",
            "spam_proposal": "Replace black-hat tactics with Google-compliant strategies.",
        }
        for v in violations:
            if v["type"] not in seen:
                seen.add(v["type"])
                out.append({"issue": v["type"], "severity": v["severity"],
                             "action": actions.get(v["type"], "Review per Google Webmaster Guidelines.")})
        return out

    def _summary(self, violations: list[dict[str, Any]], score: float) -> str:
        if not violations:
            return f"Site is policy-compliant. Compliance score: {score:.0%}."
        c = sum(1 for v in violations if v["severity"] == "critical")
        h = sum(1 for v in violations if v["severity"] == "high")
        return (f"Found {len(violations)} violations ({c} critical, {h} high). "
                f"Compliance score: {score:.0%}. Immediate action required.")
