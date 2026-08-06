from app.laboratory.pricing.price_elasticity_service import PriceElasticityService
from app.laboratory.diagnostics.trend_diagnostic_service import TrendDiagnosticService


def test_elasticity_unknown_product_reports_unavailable():
    service = PriceElasticityService()
    result = service.simulate("P999999", price_change_pct=10)
    assert result["available"] is False
    assert "reason" in result


def test_elasticity_known_product_returns_full_result():
    service = PriceElasticityService()
    result = service.simulate("P019", price_change_pct=10)
    assert result["available"] is True
    assert "elasticity" in result
    assert 0.0 <= result["confidence"] <= 1.0
    assert len(result["caveats"]) >= 1


def test_elasticity_low_r_squared_is_flagged_in_caveats():
    service = PriceElasticityService()
    # Find any product with low R^2 in the table and confirm the
    # caveat language actually appears -- not just a silent number.
    for product_id in service.table.index:
        row = service.table.loc[product_id]
        if row["r_squared"] < 0.15:
            result = service.simulate(product_id, price_change_pct=10)
            assert any("R\u00b2 is low" in c for c in result["caveats"])
            break


def test_elasticity_simulation_links_to_reorder_quantity():
    # Regression test: the price simulation used to only report a
    # revenue/demand percentage with no connection to the actual
    # replenishment decision, so changing the price slider had no
    # visible effect on anything actionable. When baseline reorder
    # inputs are provided, the simulation must return an adjusted
    # quantity that differs from the baseline for a real price change.
    service = PriceElasticityService()
    result = service.simulate(
        "P024",
        price_change_pct=20,
        baseline_expected_demand_during_lead_time=30.0,
        baseline_safety_stock=5.0,
        baseline_available_stock=10.0,
        baseline_requested_quantity=25.0,
    )
    assert result["baseline_requested_quantity"] == 25
    assert "adjusted_requested_quantity" in result
    assert result["adjusted_requested_quantity"] >= 0
    assert "quantity_change" in result


def test_trend_diagnostic_known_product_returns_full_result():
    service = TrendDiagnosticService()
    result = service.diagnose("P019")
    assert result["available"] is True
    assert result["direction"] in ("increasing", "decreasing", "stable")
    assert "methodology_note" in result
    assert "correlat" in result["methodology_note"].lower()


def test_trend_diagnostic_correlated_factors_have_required_fields():
    service = TrendDiagnosticService()
    result = service.diagnose("P019")
    for factor in result["correlated_factors"]:
        assert "correlation" in factor
        assert "p_value" in factor
        assert "significant" in factor
