from app.laboratory.synthesis.executive_summary import build_executive_summary


def _decision_context(quantity=5, service_level=0.95):
    return {
        "requested_quantity": quantity,
        "target_service_level": service_level,
    }


def _final_decision(position="APPROVE", confidence=0.9):
    return {"final_position": position, "confidence": confidence}


def test_summary_mentions_zero_quantity_when_no_order_needed():
    result = build_executive_summary(
        product_name="Test Product",
        decision_context=_decision_context(quantity=0),
        final_decision=_final_decision(),
        forecast=None,
        trend_diagnostic=None,
    )
    assert "no order needed" in result["summary"]


def test_summary_mentions_quantity_and_service_level_when_order_needed():
    result = build_executive_summary(
        product_name="Test Product",
        decision_context=_decision_context(quantity=12, service_level=0.99),
        final_decision=_final_decision(),
        forecast=None,
        trend_diagnostic=None,
    )
    assert "12 units" in result["summary"]
    assert "99%" in result["summary"]


def test_summary_incorporates_rising_forecast():
    forecast = {"trend": "increasing", "avg_forecasted_demand": 8.5, "horizon_days": 14}
    result = build_executive_summary(
        product_name="Test Product",
        decision_context=_decision_context(),
        final_decision=_final_decision(),
        forecast=forecast,
        trend_diagnostic=None,
    )
    assert "rising demand" in result["summary"]
    assert result["based_on"]["demand_forecast"] is True


def test_summary_flags_significant_correlated_factors():
    trend_diagnostic = {
        "available": True,
        "underlying_trend_change_pct": 40.0,
        "category_verdict": "product_specific",
        "category": "Soccer",
        "correlated_factors": [
            {"factor": "Discount level", "significant": True},
            {"factor": "Late delivery rate", "significant": False},
        ],
    }
    result = build_executive_summary(
        product_name="Test Product",
        decision_context=_decision_context(),
        final_decision=_final_decision(),
        forecast=None,
        trend_diagnostic=trend_diagnostic,
    )
    # Only the significant factor should be named -- not the
    # non-significant one.
    assert "discount level" in result["summary"].lower()
    assert "late delivery rate" not in result["summary"].lower()
    assert result["based_on"]["trend_diagnostic"] is True


def test_summary_omits_unavailable_sections_gracefully():
    result = build_executive_summary(
        product_name="Test Product",
        decision_context=_decision_context(),
        final_decision=_final_decision(),
        forecast=None,
        trend_diagnostic={"available": False, "reason": "not enough data"},
    )
    assert result["based_on"]["demand_forecast"] is False
    assert result["based_on"]["trend_diagnostic"] is False
    # Should still produce a valid summary from the department vote alone.
    assert len(result["summary"]) > 0
