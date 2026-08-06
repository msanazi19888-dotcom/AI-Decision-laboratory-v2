class RiskManagementAgent:

    def analyze(self, decision_context):

        suppliers = decision_context["company_data"]["suppliers"]
        finance = decision_context["company_data"]["finance"]
        policies = decision_context["company_data"]["policies"]
        products = decision_context["company_data"]["products"]
        product_id = decision_context["product_id"]

        # Evaluate carrier reliability within the product's real primary
        # market, consistent with how Logistics Agent picks a carrier --
        # otherwise Risk could flag a product as safe based on a carrier
        # reliability figure from a market that product never ships in.
        product_rows = products[products["product_id"] == product_id]
        primary_market = (
            product_rows.iloc[0].get("primary_market")
            if not product_rows.empty and "primary_market" in product_rows.columns
            else None
        )
        market_pool = (
            suppliers[suppliers["market"] == primary_market]
            if primary_market is not None and "market" in suppliers.columns
            else suppliers.iloc[0:0]
        )
        supplier_pool = market_pool if not market_pool.empty else suppliers
        best_reliability = float(supplier_pool["reliability"].max())

        available_budget = float(
            finance.loc[finance["metric"] == "available_budget", "value"].iloc[0]
        )
        cash_flow = finance.loc[finance["metric"] == "cash_flow", "value"].iloc[0]

        risk_appetite = policies["risk_appetite"]

        # Carrier reliability contributes to risk CONTINUOUSLY, not in
        # coarse buckets. The real carrier data in this market never
        # exceeds ~62% reliability at its best, so a bucket like
        # "50-80% = +20" swallowed essentially every product into the
        # same fixed contribution regardless of whether its actual best
        # option was 62% or 5% reliable. Scaling directly off
        # (100 - reliability) preserves that real spread.
        reliability_risk = round((100 - best_reliability) * 0.45, 1)

        # Second signal, genuinely product-specific: because the agent
        # always picks the SINGLE BEST carrier, and the best carrier
        # converges to roughly the same reliability (~62%) across every
        # market, carrier reliability alone barely varies between
        # products. Demand volatility does vary meaningfully -- it's
        # the ratio of this product's dynamic safety stock (which scales
        # with its own demand variability, not a flat percentage) to its
        # expected demand over the lead time. A product with unstable,
        # spiky demand carries more real operational risk than one with
        # steady demand, even against the same carrier.
        safety_stock_used = decision_context.get("safety_stock_used")
        expected_demand_during_lead_time = decision_context.get(
            "expected_demand_during_lead_time"
        )
        if safety_stock_used is not None and expected_demand_during_lead_time:
            volatility_ratio = safety_stock_used / max(expected_demand_during_lead_time, 1)
            volatility_risk = round(min(25.0, volatility_ratio * 15), 1)
        else:
            volatility_risk = 0.0

        risk_score = reliability_risk + volatility_risk

        if available_budget < 10000:
            risk_score += 30

        if cash_flow == "At Risk":
            risk_score += 25
        elif cash_flow == "Tight":
            risk_score += 10

        if risk_appetite == "Low":
            risk_score += 15

        risk_score = round(risk_score, 1)

        if risk_score >= 65:
            position = "REJECT"
            confidence = round(min(0.99, 0.7 + risk_score / 200), 2)
            reasons = ["Overall operational risk is too high."]
            concerns = ["Review supplier and financial conditions."]
        elif risk_score >= 40:
            position = "APPROVE WITH WARNING"
            confidence = round(min(0.95, 0.6 + risk_score / 200), 2)
            reasons = ["Moderate operational risk detected."]
            concerns = ["Monitor execution carefully."]
        else:
            position = "APPROVE"
            confidence = round(min(0.99, 0.85 + (40 - risk_score) / 200), 2)
            reasons = ["Overall operational risk is acceptable."]
            concerns = []

        if volatility_risk >= 15:
            reasons.append(
                "This product's demand is comparatively volatile, requiring a "
                "larger safety buffer relative to expected demand."
            )

        if cash_flow == "At Risk":
            reasons.append("Recent company-wide revenue trend is declining.")

        return {
            "agent": "Risk Management Agent",
            "position": position,
            "confidence": confidence,
            "metrics": {
                "risk_score": risk_score,
                "reliability_risk_component": reliability_risk,
                "demand_volatility_risk_component": volatility_risk,
                "best_available_carrier_reliability_pct": best_reliability,
                "risk_appetite": risk_appetite,
                "cash_flow": cash_flow,
                "primary_market": primary_market,
            },
            "reasons": reasons,
            "concerns": concerns,
        }
