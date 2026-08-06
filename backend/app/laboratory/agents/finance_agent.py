class FinanceAgent:

    def analyze(self, decision_context):

        finance = decision_context["company_data"]["finance"]
        products = decision_context["company_data"]["products"]
        product_id = decision_context["product_id"]
        requested_quantity = decision_context["requested_quantity"]

        available_budget = float(
            finance.loc[finance["metric"] == "available_budget", "value"].iloc[0]
        )
        monthly_purchase_limit = float(
            finance.loc[finance["metric"] == "monthly_purchase_limit", "value"].iloc[0]
        )
        cash_flow = finance.loc[finance["metric"] == "cash_flow", "value"].iloc[0]

        product_rows = products[products["product_id"] == product_id]
        if product_rows.empty:
            raise ValueError(f"Unknown product_id: {product_id}")
        product = product_rows.iloc[0]
        unit_cost = float(product["unit_cost"])
        selling_price = float(product["selling_price"])
        profit_margin = float(product["avg_profit_margin"]) if "avg_profit_margin" in product else None

        purchase_cost = unit_cost * requested_quantity
        expected_revenue = selling_price * requested_quantity
        expected_profit = (
            round(expected_revenue * profit_margin, 2) if profit_margin is not None else None
        )

        if requested_quantity == 0:
            # Nothing to buy -- inventory is already healthy, so this
            # is trivially fine from a finance standpoint.
            position = "APPROVE"
            confidence = 0.99
            reasons = ["No purchase is needed; requested quantity is 0."]
            concerns = []
        elif purchase_cost <= available_budget:
            position = "APPROVE"
            # Confidence reflects how much budget headroom remains --
            # a purchase that barely fits the budget is a less
            # confident APPROVE than one with lots of room to spare.
            budget_margin = 1 - (purchase_cost / available_budget)
            confidence = round(min(0.99, 0.75 + 0.24 * budget_margin), 2)
            reasons = [
                f"Purchase cost (${purchase_cost:,.2f}) is within the "
                f"available budget (${available_budget:,.2f})."
            ]
            concerns = []
        else:
            position = "REJECT"
            overage_ratio = (purchase_cost - available_budget) / available_budget
            confidence = round(min(0.99, 0.7 + 0.29 * min(overage_ratio, 1)), 2)
            reasons = [
                f"Purchase cost (${purchase_cost:,.2f}) exceeds the "
                f"available budget (${available_budget:,.2f})."
            ]
            concerns = ["Increase available budget or reduce order quantity."]

        # Cash flow trend now genuinely affects the decision, not just
        # a displayed label: a company whose real revenue trend is
        # deteriorating should be more cautious about new purchases,
        # even ones that technically fit the current budget snapshot.
        if cash_flow == "At Risk" and position == "APPROVE":
            confidence = round(confidence * 0.85, 2)
            concerns.append(
                "Recent revenue trend is declining -- approved, but with reduced confidence."
            )
        elif cash_flow == "Tight" and position == "APPROVE":
            confidence = round(confidence * 0.93, 2)

        if expected_profit is not None and requested_quantity > 0:
            reasons.append(
                f"This order is projected to generate about ${expected_profit:,.2f} "
                f"in profit at this product's average margin "
                f"({profit_margin * 100:.1f}%)."
            )

        return {
            "agent": "Finance Agent",
            "position": position,
            "confidence": confidence,
            "metrics": {
                "requested_quantity": requested_quantity,
                "purchase_cost": round(purchase_cost, 2),
                "available_budget": available_budget,
                "monthly_purchase_limit": monthly_purchase_limit,
                "cash_flow": cash_flow,
                "profit_margin_pct": round(profit_margin * 100, 1) if profit_margin is not None else None,
                "expected_profit": expected_profit,
            },
            "reasons": reasons,
            "concerns": concerns,
        }
