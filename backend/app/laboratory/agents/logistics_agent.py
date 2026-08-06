import pandas as pd


class LogisticsAgent:

    def analyze(self, decision_context):

        suppliers = decision_context["company_data"]["suppliers"]
        inventory = decision_context["company_data"]["inventory"]
        products = decision_context["company_data"]["products"]
        product_id = decision_context["product_id"]

        item_rows = inventory[inventory["product_id"] == product_id]
        if item_rows.empty:
            raise ValueError(f"No inventory record found for product_id: {product_id}")
        warehouse = item_rows.iloc[0]
        current_stock = int(warehouse["current_stock"])
        reserved_stock = int(warehouse["reserved_stock"])
        available_stock = current_stock - reserved_stock

        # Carriers are evaluated within the product's actual primary
        # market (where it real-historically sells most) when that data
        # is available -- a carrier's reliability genuinely differs by
        # region, so a Europe-bound product shouldn't be matched against
        # an Africa-route carrier's performance. Falls back to the full
        # carrier pool if the product has no market data.
        product_rows = products[products["product_id"] == product_id]
        primary_market = (
            product_rows.iloc[0].get("primary_market")
            if not product_rows.empty and "primary_market" in product_rows.columns
            else None
        )
        market_pool = (
            suppliers[suppliers["market"] == primary_market]
            if primary_market is not None and "market" in suppliers.columns
            else pd.DataFrame()
        )
        supplier_pool = market_pool if not market_pool.empty else suppliers

        # Suppliers here represent shipping carriers, not per-product
        # vendors, so the agent evaluates ALL of them (within the
        # relevant market) and recommends the best fit -- not just
        # whichever row happens to be first.
        reliable = supplier_pool[supplier_pool["reliability"] >= 50]
        candidates = reliable if not reliable.empty else supplier_pool
        best = candidates.sort_values(
            by=["reliability", "lead_time_days"], ascending=[False, True]
        ).iloc[0]

        supplier_name = best["supplier_name"]
        lead_time = float(best["lead_time_days"])
        reliability = float(best["reliability"])

        if reliability < 50:
            position = "REJECT"
            confidence = round(min(0.99, 0.7 + (50 - reliability) / 100), 2)
            reasons = ["No carrier meets the acceptable reliability threshold."]
            concerns = ["Review carrier options; all available carriers are unreliable."]
        elif lead_time > 5:
            position = "APPROVE WITH WARNING"
            confidence = round(min(0.95, 0.7 + reliability / 200), 2)
            reasons = [f"Best available carrier ({supplier_name}) has a longer lead time."]
            concerns = ["Delivery delay may increase stock-out risk."]
        else:
            position = "APPROVE"
            confidence = round(min(0.99, 0.75 + reliability / 200), 2)
            reasons = [f"{supplier_name} is reliable and delivery time is acceptable."]
            concerns = []

        if primary_market is not None and not market_pool.empty:
            reasons.append(
                f"Evaluated against carriers serving this product's primary market "
                f"({primary_market}), not the full carrier pool."
            )

        return {
            "agent": "Logistics Agent",
            "position": position,
            "confidence": confidence,
            "metrics": {
                "recommended_carrier": supplier_name,
                "lead_time_days": lead_time,
                "carrier_reliability_pct": reliability,
                "available_stock": available_stock,
                "primary_market": primary_market,
            },
            "reasons": reasons,
            "concerns": concerns,
        }
