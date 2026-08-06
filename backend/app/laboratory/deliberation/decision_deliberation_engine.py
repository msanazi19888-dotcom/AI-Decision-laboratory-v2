class DecisionDeliberationEngine:
    """
    Resolves the four department opinions into one final decision.

    Finance and Risk keep veto power (a hard REJECT from either one
    stops the process, since those are compliance/safety gates, not
    just another vote). But when nobody vetoes -- the most common
    real-world case -- this now actually produces a final decision
    using the organization's own weighting policy, instead of
    returning "UNDER DELIBERATION" with confidence 0.0 forever.
    """

    DEFAULT_WEIGHTS = {
        "finance_weight": 25,
        "inventory_weight": 25,
        "logistics_weight": 25,
        "risk_weight": 25,
    }

    def deliberate(
        self,
        finance_opinion,
        inventory_opinion,
        logistics_opinion,
        risk_opinion,
        policy_weights=None,
    ):
        votes = {
            "finance": finance_opinion["position"],
            "inventory": inventory_opinion["position"],
            "logistics": logistics_opinion["position"],
            "risk": risk_opinion["position"],
        }

        if finance_opinion["position"] == "REJECT":
            return {
                "final_position": "REJECT",
                "confidence": finance_opinion["confidence"],
                "reason": "Finance Department rejected the decision.",
                "department_votes": votes,
            }

        if risk_opinion["position"] == "REJECT":
            return {
                "final_position": "REJECT",
                "confidence": risk_opinion["confidence"],
                "reason": "Risk Management rejected the decision.",
                "department_votes": votes,
            }

        # No veto -- combine the four confidences using the org's
        # decision-policy weights (finance_weight / inventory_weight /
        # logistics_weight / risk_weight from policies.json).
        weights = policy_weights or self.DEFAULT_WEIGHTS
        total_weight = sum(weights.values()) or 1

        weighted_confidence = (
            finance_opinion["confidence"] * weights.get("finance_weight", 25)
            + inventory_opinion["confidence"] * weights.get("inventory_weight", 25)
            + logistics_opinion["confidence"] * weights.get("logistics_weight", 25)
            + risk_opinion["confidence"] * weights.get("risk_weight", 25)
        ) / total_weight

        opinions = [finance_opinion, inventory_opinion, logistics_opinion, risk_opinion]
        has_warning = any(o["position"] == "APPROVE WITH WARNING" for o in opinions)

        if has_warning:
            final_position = "APPROVE WITH CONDITIONS"
            reason = (
                "All departments approve, but one or more raised a warning "
                "that should be monitored."
            )
        else:
            final_position = "APPROVE"
            reason = "All departments approve with acceptable confidence."

        all_concerns = [c for o in opinions for c in o.get("concerns", [])]

        return {
            "final_position": final_position,
            "confidence": round(weighted_confidence, 2),
            "reason": reason,
            "department_votes": votes,
            "concerns": all_concerns,
        }
