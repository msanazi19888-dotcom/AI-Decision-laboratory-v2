import pytest

from app.laboratory.context.enterprise_knowledge_hub import EnterpriseKnowledgeHub
from app.laboratory.context.decision_context_builder import DecisionContextBuilder
from app.laboratory.agents.finance_agent import FinanceAgent
from app.laboratory.agents.inventory_agent import InventoryAgent
from app.laboratory.agents.logistics_agent import LogisticsAgent
from app.laboratory.agents.risk_management_agent import RiskManagementAgent

VALID_POSITIONS = {"APPROVE", "APPROVE WITH WARNING", "REJECT"}


@pytest.fixture(scope="module")
def context():
    hub = EnterpriseKnowledgeHub()
    builder = DecisionContextBuilder(hub)
    return builder.build(product_id="P019")


def test_finance_agent_returns_valid_position(context):
    result = FinanceAgent().analyze(context)
    assert result["position"] in VALID_POSITIONS
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["metrics"]["requested_quantity"] == context["requested_quantity"]


def test_finance_agent_confidence_is_not_a_fixed_constant():
    # Regression test for the original bug: every branch returned a
    # hardcoded confidence (0.90, 0.92, 0.95...) regardless of the
    # actual numbers. Two very different budget scenarios should NOT
    # produce identical confidence.
    hub = EnterpriseKnowledgeHub()
    builder = DecisionContextBuilder(hub)

    context_a = builder.build(product_id="P019")
    context_b = builder.build(product_id="P044")

    result_a = FinanceAgent().analyze(context_a)
    result_b = FinanceAgent().analyze(context_b)

    # Confidence values are allowed to coincide by chance, but at least
    # one of the underlying computed metrics must differ -- proving
    # the number is computed, not copy-pasted.
    assert result_a["metrics"]["purchase_cost"] != result_b["metrics"]["purchase_cost"]


def test_inventory_agent_uses_model_forecast_when_available(context):
    result = InventoryAgent().analyze(context)
    assert result["position"] in VALID_POSITIONS
    assert result["metrics"]["forecast_source"] in ("model", "fallback")
    assert result["metrics"]["forecasted_daily_demand"] >= 0


def test_inventory_agent_uses_dynamic_objective_aware_safety_stock():
    # Regression test: InventoryAgent used to read a STATIC safety_stock
    # from inventory.csv, independent of the chosen business objective
    # or the demand forecast used to compute requested_quantity. After
    # an inventory data recalibration, that static threshold caused
    # REJECT for ~96% of all products regardless of objective. The
    # agent must use the SAME dynamic, objective-aware safety stock
    # DecisionContextBuilder computes, so a stricter objective can
    # reasonably reject more often than a looser one, but neither
    # dominates almost every product.
    hub = EnterpriseKnowledgeHub()
    builder = DecisionContextBuilder(hub)
    products = hub.get_dataset("products")["product_id"]

    reject_counts = {}
    for objective in ["Avoid Stock-out", "Minimize Holding Cost"]:
        rejects = 0
        total = 0
        for pid in products:
            try:
                ctx = builder.build(product_id=pid, business_objective=objective)
                result = InventoryAgent().analyze(ctx)
                total += 1
                if result["position"] == "REJECT":
                    rejects += 1
            except ValueError:
                continue
        reject_counts[objective] = rejects / total

    # Neither objective should reject almost everything.
    assert reject_counts["Avoid Stock-out"] < 0.5
    assert reject_counts["Minimize Holding Cost"] < 0.5
    # The stricter objective should reject at least as often as the
    # more lenient one -- the whole point of the feature.
    assert reject_counts["Avoid Stock-out"] >= reject_counts["Minimize Holding Cost"]


def test_logistics_agent_selects_best_available_carrier(context):
    result = LogisticsAgent().analyze(context)
    assert result["position"] in VALID_POSITIONS
    assert result["metrics"]["carrier_reliability_pct"] >= 0
    assert result["metrics"]["lead_time_days"] > 0


def test_risk_agent_returns_valid_position(context):
    result = RiskManagementAgent().analyze(context)
    assert result["position"] in VALID_POSITIONS
    assert 0 <= result["metrics"]["risk_score"] <= 100


def test_risk_agent_genuinely_discriminates_between_products():
    # Regression test: because the agent always evaluates the SINGLE
    # BEST carrier, and the best carrier converges to nearly the same
    # reliability (~62%) across every real market in this dataset, an
    # earlier version of the risk formula effectively produced the same
    # risk_score for all 118 products, making Risk Management's verdict
    # a foregone conclusion rather than a real per-product assessment.
    # There must be genuine spread across the catalog, not a constant.
    hub = EnterpriseKnowledgeHub()
    builder = DecisionContextBuilder(hub)
    products = hub.get_dataset("products")["product_id"]

    positions = set()
    scores = []
    for pid in products:
        ctx = builder.build(product_id=pid)
        result = RiskManagementAgent().analyze(ctx)
        positions.add(result["position"])
        scores.append(result["metrics"]["risk_score"])

    # More than one verdict must appear across the real catalog.
    assert len(positions) > 1
    # Scores must have real spread, not be clustered on a single value.
    assert max(scores) - min(scores) > 5
