from app.laboratory.models.decision_context import DecisionContext
from app.laboratory.forecasting.demand_forecast_service import (
    DemandForecastService,
)

_forecast_service = None


def _get_forecast_service():
    global _forecast_service
    if _forecast_service is None:
        _forecast_service = DemandForecastService()
    return _forecast_service


# Each business objective maps to a target service level (probability
# of NOT stocking out during the lead time window), which in turn maps
# to a Z-score via the standard normal distribution -- the same
# safety-stock methodology used in the companion demand-forecasting
# project. This is what makes business_objective actually change the
# decision instead of being a display-only label.
OBJECTIVE_SERVICE_LEVELS = {
    "Avoid Stock-out": 0.99,
    "Balanced": 0.95,
    "Minimize Holding Cost": 0.90,
}

SERVICE_LEVEL_Z = {
    0.90: 1.28,
    0.95: 1.65,
    0.99: 2.33,
}


class DecisionContextBuilder:
    """
    Builds a structured DecisionContext for a SPECIFIC product, rather
    than defaulting to the first row of every dataset. This is what
    lets every decision actually respond to the product the manager
    selected, instead of always analyzing the same hardcoded item.
    """

    def __init__(self, knowledge_hub):
        self.knowledge_hub = knowledge_hub

    def build(self, product_id: str, priority: str = "High",
              business_objective: str = "Avoid Stock-out"):
        data = self.knowledge_hub.get_all()

        products = data["products"]
        inventory = data["inventory"]
        suppliers = data["suppliers"]
        sales = data["sales"]

        if business_objective not in OBJECTIVE_SERVICE_LEVELS:
            raise ValueError(
                f"Unknown business_objective: {business_objective!r}. "
                f"Must be one of {list(OBJECTIVE_SERVICE_LEVELS.keys())}."
            )

        product_rows = products[products["product_id"] == product_id]
        if product_rows.empty:
            raise ValueError(f"Unknown product_id: {product_id}")

        inventory_rows = inventory[inventory["product_id"] == product_id]
        if inventory_rows.empty:
            raise ValueError(f"No inventory record found for product_id: {product_id}")

        inventory_item = inventory_rows.iloc[0]
        current_stock = int(inventory_item["current_stock"])
        reserved_stock = int(inventory_item["reserved_stock"])
        static_safety_stock = int(inventory_item["safety_stock"])
        reorder_point = int(inventory_item["reorder_point"])
        available_stock = current_stock - reserved_stock

        # Lead time used for planning: the average across all available
        # carriers (a conservative planning assumption, since the
        # specific carrier isn't chosen until the Logistics Agent runs).
        avg_lead_time_days = max(1, round(float(suppliers["lead_time_days"].mean())))

        service_level = OBJECTIVE_SERVICE_LEVELS[business_objective]
        z_score = SERVICE_LEVEL_Z[service_level]

        # Real demand volatility for THIS product, from its own sales
        # history -- a volatile product gets a bigger safety buffer
        # than a stable one, for the same objective.
        product_sales = sales[sales["product_id"] == product_id]["quantity_sold"]
        demand_std = float(product_sales.std()) if len(product_sales) > 1 else 0.0

        forecast_source = "model"
        try:
            horizon = _get_forecast_service().predict_horizon(
                product_id, days=avg_lead_time_days
            )
            # Expected demand over the FULL lead time, not just tomorrow --
            # this is what actually determines how much to order: enough
            # to cover demand until the next delivery arrives, plus a
            # safety buffer sized to the chosen business objective.
            expected_demand_during_lead_time = sum(
                p["predicted_demand"] for p in horizon["points"]
            )
            dynamic_safety_stock = z_score * demand_std * (avg_lead_time_days ** 0.5)
            target_stock_level = expected_demand_during_lead_time + dynamic_safety_stock
            requested_quantity = max(0, round(target_stock_level - available_stock))
            safety_stock_used = round(dynamic_safety_stock, 1)
        except ValueError:
            # No sales history for this product -- fall back to the
            # static reorder-point policy rather than crashing.
            forecast_source = "fallback"
            avg_lead_time_days = None
            expected_demand_during_lead_time = None
            target_stock_level = reorder_point + static_safety_stock
            requested_quantity = max(0, target_stock_level - available_stock)
            safety_stock_used = static_safety_stock

        context = DecisionContext(
            decision_type="Inventory Replenishment",
            business_objective=business_objective,
            priority=priority,
            product_id=product_id,
            requested_quantity=requested_quantity,
            company_data=data,
        )

        context_dict = context.to_dict()
        context_dict["planning_lead_time_days"] = avg_lead_time_days
        context_dict["expected_demand_during_lead_time"] = (
            round(expected_demand_during_lead_time, 2)
            if expected_demand_during_lead_time is not None else None
        )
        context_dict["quantity_planning_source"] = forecast_source
        context_dict["target_service_level"] = service_level
        context_dict["safety_stock_used"] = safety_stock_used

        return context_dict
