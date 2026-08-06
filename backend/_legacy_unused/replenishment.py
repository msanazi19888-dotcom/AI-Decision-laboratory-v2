from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.decision_service import DecisionService

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])
decision_service = DecisionService()


class ReplenishmentRequest(BaseModel):
    product_id: str
    business_objective: str
    priority: str = "medium"
    time_horizon: str = "30_days"
    current_stock: int = 120
    daily_sales: int | None = None
    supplier_lead_time: int = 7
    safety_stock: int = 50
    warehouse_capacity: int = 500
    budget: float = 10_000.0
    unit_cost: float = 10.0


def _strategy_to_dict(strategy):
    return {
        "id": strategy.id,
        "name": strategy.name,
        "description": strategy.description,
        "expected_impact": strategy.expected_impact,
        "score": strategy.score,
    }


def _recommendation_to_dict(recommendation):
    if recommendation is None:
        return None
    return {
        "confidence": recommendation.confidence,
        "evaluation_score": recommendation.evaluation_score,
        "explanation": recommendation.explanation,
        "status": recommendation.status,
    }


@router.post("/replenishment")
def create_replenishment_decision(request: ReplenishmentRequest):
    decision = decision_service.create_replenishment_decision(
        product_id=request.product_id,
        business_objective=request.business_objective,
        priority=request.priority,
        time_horizon=request.time_horizon,
        current_stock=request.current_stock,
        daily_sales=request.daily_sales,
        supplier_lead_time=request.supplier_lead_time,
        safety_stock=request.safety_stock,
        warehouse_capacity=request.warehouse_capacity,
        budget=request.budget,
        unit_cost=request.unit_cost,
    )

    context = decision.context
    selected_strategy = decision.selected_strategy

    return {
        "decision_id": decision.id,
        "status": decision.status.value,
        "decision_type": decision.decision_type.value,
        "selected_strategy": _strategy_to_dict(selected_strategy) if selected_strategy else None,
        "recommendation": _recommendation_to_dict(decision.recommendation),
        "strategies": [_strategy_to_dict(strategy) for strategy in decision.strategies],
        "context": {
            "product_id": context.product_id if context else None,
            "business_objective": context.business_objective if context else None,
            "priority": context.priority if context else None,
            "time_horizon": context.time_horizon if context else None,
            "business_data": context.business_data if context else {},
            "constraints": context.constraints if context else [],
            "policies": context.policies if context else [],
            "external_events": context.external_events if context else [],
        },
    }


@router.get("/")
def list_decisions():
    decisions = decision_service.list_decisions()
    return [
        {
            "decision_id": d.id,
            "status": d.status.value,
            "decision_type": d.decision_type.value,
        }
        for d in decisions
    ]


@router.get("/{decision_id}")
def get_decision(decision_id: str):
    decision = decision_service.get_decision(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")

    context = decision.context
    selected_strategy = decision.selected_strategy

    return {
        "decision_id": decision.id,
        "status": decision.status.value,
        "decision_type": decision.decision_type.value,
        "selected_strategy": _strategy_to_dict(selected_strategy) if selected_strategy else None,
        "recommendation": _recommendation_to_dict(decision.recommendation),
        "strategies": [_strategy_to_dict(strategy) for strategy in decision.strategies],
        "context": {
            "product_id": context.product_id if context else None,
            "business_objective": context.business_objective if context else None,
            "priority": context.priority if context else None,
            "time_horizon": context.time_horizon if context else None,
            "business_data": context.business_data if context else {},
            "constraints": context.constraints if context else [],
            "policies": context.policies if context else [],
            "external_events": context.external_events if context else [],
        },
    }