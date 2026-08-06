from app.laboratory.deliberation.decision_deliberation_engine import (
    DecisionDeliberationEngine,
)


def _opinion(position, confidence, concerns=None):
    return {"position": position, "confidence": confidence, "concerns": concerns or []}


def test_finance_reject_vetoes_regardless_of_others():
    engine = DecisionDeliberationEngine()
    result = engine.deliberate(
        finance_opinion=_opinion("REJECT", 0.9),
        inventory_opinion=_opinion("APPROVE", 0.9),
        logistics_opinion=_opinion("APPROVE", 0.9),
        risk_opinion=_opinion("APPROVE", 0.9),
    )
    assert result["final_position"] == "REJECT"


def test_risk_reject_vetoes_regardless_of_others():
    engine = DecisionDeliberationEngine()
    result = engine.deliberate(
        finance_opinion=_opinion("APPROVE", 0.9),
        inventory_opinion=_opinion("APPROVE", 0.9),
        logistics_opinion=_opinion("APPROVE", 0.9),
        risk_opinion=_opinion("REJECT", 0.9),
    )
    assert result["final_position"] == "REJECT"


def test_all_approve_resolves_to_approve_not_stuck_state():
    # Regression test for the original bug: when nobody vetoed, the
    # engine returned "UNDER DELIBERATION" with confidence 0.0 forever
    # -- the most common real-world case never reached a decision.
    engine = DecisionDeliberationEngine()
    result = engine.deliberate(
        finance_opinion=_opinion("APPROVE", 0.9),
        inventory_opinion=_opinion("APPROVE", 0.9),
        logistics_opinion=_opinion("APPROVE", 0.9),
        risk_opinion=_opinion("APPROVE", 0.9),
    )
    assert result["final_position"] == "APPROVE"
    assert result["confidence"] > 0.0


def test_warning_without_veto_produces_conditional_approval():
    engine = DecisionDeliberationEngine()
    result = engine.deliberate(
        finance_opinion=_opinion("APPROVE", 0.9),
        inventory_opinion=_opinion("APPROVE WITH WARNING", 0.8),
        logistics_opinion=_opinion("APPROVE", 0.9),
        risk_opinion=_opinion("APPROVE", 0.9),
    )
    assert result["final_position"] == "APPROVE WITH CONDITIONS"


def test_confidence_uses_policy_weights_not_a_flat_average():
    engine = DecisionDeliberationEngine()

    heavy_finance_weights = {
        "finance_weight": 90, "inventory_weight": 5,
        "logistics_weight": 3, "risk_weight": 2,
    }
    result = engine.deliberate(
        finance_opinion=_opinion("APPROVE", 0.99),
        inventory_opinion=_opinion("APPROVE", 0.10),
        logistics_opinion=_opinion("APPROVE", 0.10),
        risk_opinion=_opinion("APPROVE", 0.10),
        policy_weights=heavy_finance_weights,
    )
    # With finance weighted at 90%, overall confidence should track
    # much closer to finance's 0.99 than to a flat average (~0.32).
    assert result["confidence"] > 0.7
