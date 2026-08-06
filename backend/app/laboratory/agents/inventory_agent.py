from app.laboratory.forecasting.demand_forecast_service import DemandForecastService

_forecast_service = None


def _get_forecast_service():
    global _forecast_service
    if _forecast_service is None:
        _forecast_service = DemandForecastService()
    return _forecast_service


class InventoryAgent:

    def analyze(self, decision_context):

        inventory = decision_context["company_data"]["inventory"]
        sales = decision_context["company_data"]["sales"]
        products = decision_context["company_data"]["products"]
        product_id = decision_context["product_id"]
        requested_quantity = decision_context["requested_quantity"]

        item_rows = inventory[inventory["product_id"] == product_id]
        if item_rows.empty:
            raise ValueError(f"No inventory record found for product_id: {product_id}")
        item = item_rows.iloc[0]

        current_stock = int(item["current_stock"])
        reserved_stock = int(item["reserved_stock"])
        static_safety_stock = int(item["safety_stock"])
        static_reorder_point = int(item["reorder_point"])

        # Use the SAME dynamic, objective-aware safety stock that
        # DecisionContextBuilder already computed for the quantity
        # decision -- not the static inventory.csv figures. Without
        # this, the chosen business objective (and the demand forecast)
        # would change the requested quantity but silently NOT change
        # whether Inventory approves or rejects, which is inconsistent
        # and was producing REJECT for the large majority of products
        # regardless of objective.
        dynamic_safety_stock = decision_context.get("safety_stock_used")
        expected_demand_during_lead_time = decision_context.get(
            "expected_demand_during_lead_time"
        )
        if dynamic_safety_stock is not None and expected_demand_during_lead_time is not None:
            safety_stock = dynamic_safety_stock
            reorder_point = expected_demand_during_lead_time + dynamic_safety_stock
        else:
            # No forecast available for this product -- fall back to
            # the static policy rather than crashing.
            safety_stock = static_safety_stock
            reorder_point = static_reorder_point

        # Demand estimate now comes from the trained LightGBM forecasting
        # model (real historical patterns per product), not a flat
        # historical average. Falls back to the historical mean only if
        # the model has no history for this product.
        forecast_source = "model"
        try:
            forecast = _get_forecast_service().predict_next_day(product_id)
            average_daily_sales = forecast["predicted_next_day_demand"]
            forecast_confidence = forecast["confidence"]
        except ValueError:
            forecast_source = "fallback"
            product_sales = sales[sales["product_id"] == product_id]
            average_daily_sales = (
                float(product_sales["quantity_sold"].mean()) if not product_sales.empty else 0.0
            )
            forecast_confidence = 0.5

        product_rows = products[products["product_id"] == product_id]
        product_name = product_rows.iloc[0]["product_name"] if not product_rows.empty else product_id

        available_stock = current_stock - reserved_stock
        days_until_stockout = (
            round(available_stock / average_daily_sales, 1)
            if average_daily_sales > 0 else None
        )

        if available_stock <= safety_stock:
            position = "REJECT"
            # The further below safety stock, the more confident the alert.
            deficit_ratio = (
                (safety_stock - available_stock) / safety_stock if safety_stock > 0 else 1.0
            )
            base_confidence = min(0.99, 0.8 + 0.19 * min(deficit_ratio, 1))
            reasons = ["Available stock is below the safety stock level."]
            concerns = ["Immediate replenishment is required."]

        elif available_stock <= reorder_point:
            position = "APPROVE WITH WARNING"
            proximity_to_safety = (
                (reorder_point - available_stock) / max(reorder_point - safety_stock, 1)
            )
            base_confidence = min(0.97, 0.75 + 0.2 * proximity_to_safety)
            reasons = ["Stock has reached the reorder point."]
            concerns = ["Place a replenishment order soon."]

        else:
            position = "APPROVE"
            headroom_ratio = (
                (available_stock - reorder_point) / max(reorder_point, 1)
            )
            base_confidence = min(0.99, 0.8 + 0.19 * min(headroom_ratio, 1))
            reasons = ["Inventory level is healthy."]
            concerns = []

        # Blend the inventory-rule confidence with the forecast model's
        # own confidence -- a healthy-looking stock position based on an
        # unreliable demand forecast shouldn't be reported as fully
        # confident.
        confidence = round((base_confidence * 0.7) + (forecast_confidence * 0.3), 2)

        if forecast_source == "model":
            reasons.append(
                f"Demand forecast ({average_daily_sales} units/day) was produced by the "
                f"trained LightGBM model from this product's sales history."
            )

        return {
            "agent": "Inventory Agent",
            "position": position,
            "confidence": confidence,
            "metrics": {
                "product": product_name,
                "current_stock": current_stock,
                "reserved_stock": reserved_stock,
                "available_stock": available_stock,
                "safety_stock": round(safety_stock, 1),
                "reorder_point": round(reorder_point, 1),
                "static_safety_stock_reference": static_safety_stock,
                "forecasted_daily_demand": round(average_daily_sales, 2),
                "forecast_source": forecast_source,
                "forecast_confidence": forecast_confidence,
                "days_until_stockout": days_until_stockout,
                "requested_quantity": requested_quantity,
                "target_service_level": decision_context.get("target_service_level"),
            },
            "reasons": reasons,
            "concerns": concerns,
        }
