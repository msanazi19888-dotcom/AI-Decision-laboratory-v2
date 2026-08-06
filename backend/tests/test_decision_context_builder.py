import pytest

from app.laboratory.context.enterprise_knowledge_hub import EnterpriseKnowledgeHub
from app.laboratory.context.decision_context_builder import DecisionContextBuilder


@pytest.fixture(scope="module")
def builder():
    hub = EnterpriseKnowledgeHub()
    return DecisionContextBuilder(hub)


def test_unknown_product_raises_value_error(builder):
    with pytest.raises(ValueError, match="Unknown product_id"):
        builder.build(product_id="P999999")


def test_known_product_returns_context_with_required_fields(builder):
    context = builder.build(product_id="P019")

    assert context["product_id"] == "P019"
    assert context["decision_type"] == "Inventory Replenishment"
    assert isinstance(context["requested_quantity"], (int, float))
    assert context["requested_quantity"] >= 0


def test_requested_quantity_differs_across_products(builder):
    # Regression test for the original bug where every agent always
    # analyzed the first row regardless of which product was requested.
    context_a = builder.build(product_id="P019")
    context_b = builder.build(product_id="P044")

    assert context_a["product_id"] != context_b["product_id"]
    # Not a strict inequality on quantity (they COULD coincidentally
    # match), but the two contexts must be independently computed --
    # verified here by checking their lead-time demand figures differ,
    # which would be identical only if the context builder were still
    # reading a single hardcoded row.
    assert (
        context_a["expected_demand_during_lead_time"]
        != context_b["expected_demand_during_lead_time"]
    )


def test_quantity_planning_uses_lead_time_forecast_when_available(builder):
    context = builder.build(product_id="P019")

    assert context["quantity_planning_source"] == "model"
    assert context["planning_lead_time_days"] is not None
    assert context["planning_lead_time_days"] > 0
    assert context["expected_demand_during_lead_time"] is not None


def test_unknown_business_objective_raises_value_error(builder):
    with pytest.raises(ValueError, match="Unknown business_objective"):
        builder.build(product_id="P019", business_objective="Not A Real Objective")


def test_business_objective_changes_safety_stock_and_quantity(builder):
    # Regression test: business_objective was previously a display-only
    # label with no effect on the actual decision. It must now change
    # both the safety-stock buffer and (for at least some products)
    # the final requested quantity.
    stockout_avoidant = builder.build(
        product_id="P024", business_objective="Avoid Stock-out"
    )
    cost_minimizing = builder.build(
        product_id="P024", business_objective="Minimize Holding Cost"
    )

    assert stockout_avoidant["target_service_level"] == 0.99
    assert cost_minimizing["target_service_level"] == 0.90
    assert stockout_avoidant["safety_stock_used"] > cost_minimizing["safety_stock_used"]
    assert stockout_avoidant["requested_quantity"] >= cost_minimizing["requested_quantity"]
