from fastapi import APIRouter, HTTPException

from app.laboratory.context.enterprise_knowledge_hub import (
    EnterpriseKnowledgeHub,
)

from app.laboratory.context.decision_context_builder import (
    DecisionContextBuilder,
)

from app.laboratory.agents.finance_agent import FinanceAgent
from app.laboratory.agents.inventory_agent import InventoryAgent
from app.laboratory.agents.logistics_agent import LogisticsAgent
from app.laboratory.agents.risk_management_agent import (
    RiskManagementAgent,
)

from app.laboratory.deliberation.decision_deliberation_engine import (
    DecisionDeliberationEngine,
)

from app.laboratory.forecasting.demand_forecast_service import (
    DemandForecastService,
)

from app.laboratory.pricing.price_elasticity_service import (
    PriceElasticityService,
)

from app.laboratory.diagnostics.trend_diagnostic_service import (
    TrendDiagnosticService,
)

from app.laboratory.persistence.decision_repository import (
    save_decision,
    list_decisions,
    get_decision,
)

from app.laboratory.synthesis.executive_summary import build_executive_summary

router = APIRouter(
    prefix="/api/v2/demo-company",
    tags=["Demo Company"],
)

_forecast_service = None
_elasticity_service = None
_trend_service = None


def _get_forecast_service():
    global _forecast_service
    if _forecast_service is None:
        _forecast_service = DemandForecastService()
    return _forecast_service


def _get_elasticity_service():
    global _elasticity_service
    if _elasticity_service is None:
        _elasticity_service = PriceElasticityService()
    return _elasticity_service


def _get_trend_service():
    global _trend_service
    if _trend_service is None:
        _trend_service = TrendDiagnosticService()
    return _trend_service


@router.get("/forecast")
def get_demand_forecast(product_id: str, days: int = 14):
    """Standalone demand forecast for a product, independent of a full
    replenishment decision -- powers the frontend forecast chart."""
    try:
        return _get_forecast_service().predict_horizon(product_id, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/pricing")
def simulate_price_change(product_id: str, price_change_pct: float = 10.0):
    """Simulates the effect of a proposed price change on demand,
    revenue, AND the actual reorder quantity -- so the panel answers
    not just "what happens to revenue" but "does this change what I
    should buy", using the same baseline reorder math the real
    replenishment decision uses."""
    baseline_kwargs = {}
    try:
        hub = EnterpriseKnowledgeHub()
        builder = DecisionContextBuilder(hub)
        ctx = builder.build(product_id=product_id)
        inventory = ctx["company_data"]["inventory"]
        item_rows = inventory[inventory["product_id"] == product_id]
        if not item_rows.empty and ctx.get("expected_demand_during_lead_time") is not None:
            item = item_rows.iloc[0]
            available_stock = int(item["current_stock"]) - int(item["reserved_stock"])
            baseline_kwargs = {
                "baseline_expected_demand_during_lead_time": ctx["expected_demand_during_lead_time"],
                "baseline_safety_stock": ctx["safety_stock_used"],
                "baseline_available_stock": available_stock,
                "baseline_requested_quantity": ctx["requested_quantity"],
            }
    except ValueError:
        pass  # unknown product -- elasticity service will report unavailable

    return _get_elasticity_service().simulate(product_id, price_change_pct, **baseline_kwargs)


@router.get("/trend-diagnostic")
def get_trend_diagnostic(product_id: str):
    """Diagnoses whether recent demand movement is a genuine trend or
    normal seasonality, and reports statistically correlated factors."""
    try:
        return _get_trend_service().diagnose(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def serialize_company_data(company_data):
    result = {}

    for key, value in company_data.items():
        if hasattr(value, "to_dict"):
            result[key] = value.to_dict(orient="records")
        else:
            result[key] = value

    return result


from app.laboratory.context.decision_context_builder import (
    OBJECTIVE_SERVICE_LEVELS,
)


@router.get("/objectives")
def list_business_objectives():
    """Lists the available business objectives and the service level
    each one targets, so the frontend can offer a real choice instead
    of a fixed display label."""
    return [
        {"objective": name, "target_service_level": level}
        for name, level in OBJECTIVE_SERVICE_LEVELS.items()
    ]


@router.get("/products")
def list_products():
    """List all available products so the frontend can offer a real
    product picker instead of always analyzing the same hardcoded item."""
    hub = EnterpriseKnowledgeHub()
    products = hub.get_dataset("products")
    return products[["product_id", "product_name", "category"]].to_dict(orient="records")


@router.get("/")
def get_demo_company(product_id: str = "P019", business_objective: str = "Avoid Stock-out"):

    # Load Company
    hub = EnterpriseKnowledgeHub()

    # Build Decision Context for the REQUESTED product and objective --
    # not a fixed one
    builder = DecisionContextBuilder(hub)
    try:
        decision_context = builder.build(
            product_id=product_id, business_objective=business_objective
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Finance Department
    finance_agent = FinanceAgent()
    finance_opinion = finance_agent.analyze(decision_context)

    # Inventory Department
    inventory_agent = InventoryAgent()
    inventory_opinion = inventory_agent.analyze(decision_context)

    # Logistics Department
    logistics_agent = LogisticsAgent()
    logistics_opinion = logistics_agent.analyze(decision_context)

    # Risk Management Department
    risk_agent = RiskManagementAgent()
    risk_opinion = risk_agent.analyze(decision_context)

    # Decision Deliberation -- pass the org's real weighting policy
    policies = decision_context["company_data"]["policies"]
    policy_weights = policies.get("decision_policy")

    deliberation_engine = DecisionDeliberationEngine()

    final_decision = deliberation_engine.deliberate(
        finance_opinion,
        inventory_opinion,
        logistics_opinion,
        risk_opinion,
        policy_weights=policy_weights,
    )

    # Convert DataFrames to JSON
    response_context = {
        "decision_type": decision_context["decision_type"],
        "business_objective": decision_context["business_objective"],
        "priority": decision_context["priority"],
        "product_id": decision_context["product_id"],
        "requested_quantity": decision_context["requested_quantity"],
        "planning_lead_time_days": decision_context.get("planning_lead_time_days"),
        "expected_demand_during_lead_time": decision_context.get(
            "expected_demand_during_lead_time"
        ),
        "quantity_planning_source": decision_context.get("quantity_planning_source"),
        "target_service_level": decision_context.get("target_service_level"),
        "safety_stock_used": decision_context.get("safety_stock_used"),
        "company_data": serialize_company_data(
            decision_context["company_data"]
        ),
    }

    product_row = hub.get_dataset("products")
    product_row = product_row[product_row["product_id"] == product_id]
    product_name = (
        product_row.iloc[0]["product_name"] if not product_row.empty else product_id
    )

    # Pull in the SAME forecast and trend-diagnostic results the
    # frontend displays elsewhere on the page, so the executive
    # summary is built from -- and only from -- evidence the person
    # can also see directly, not a separate hidden computation.
    forecast_for_summary = None
    trend_for_summary = None
    try:
        forecast_for_summary = _get_forecast_service().predict_horizon(product_id, days=14)
    except ValueError:
        pass
    try:
        trend_for_summary = _get_trend_service().diagnose(product_id)
    except ValueError:
        pass

    executive_summary = build_executive_summary(
        product_name=product_name,
        decision_context=response_context,
        final_decision=final_decision,
        forecast=forecast_for_summary,
        trend_diagnostic=trend_for_summary,
    )

    response = {
        "decision_context": response_context,

        "organizational_analysis": {

            "finance": finance_opinion,

            "inventory": inventory_opinion,

            "logistics": logistics_opinion,

            "risk": risk_opinion,
        },

        "final_decision": final_decision,

        "executive_summary": executive_summary,
    }

    decision_id = save_decision(
        product_id=product_id,
        product_name=product_name,
        decision_context=decision_context,
        final_decision=final_decision,
        full_response=response,
    )
    response["decision_id"] = decision_id

    return response


@router.get("/decisions")
def get_decision_history(limit: int = 50):
    """Lists past decisions -- previously every decision was computed
    and immediately discarded, with no history kept at all."""
    return list_decisions(limit=limit)


@router.get("/decisions/{decision_id}")
def get_decision_by_id(decision_id: int):
    decision = get_decision(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision