"""
Builds the executive summary paragraph shown with the final
recommendation, by combining the REAL numbers already computed by the
other services (demand forecast, trend diagnostic, department vote)
into a single coherent explanation -- rather than the final
recommendation being based only on the four department votes while
the forecast and trend diagnostic sit next to it, unreferenced.

This is deliberately template-based on real computed values, not a
generative model: every sentence traces back to a specific number the
person can see elsewhere on the same page. That is what keeps it
explainable -- there is no step where the reasoning could be quietly
different from the displayed evidence.
"""


def build_executive_summary(
    product_name: str,
    decision_context: dict,
    final_decision: dict,
    forecast: dict | None,
    trend_diagnostic: dict | None,
) -> dict:
    sentences = []

    position = final_decision["final_position"]
    confidence_pct = round(final_decision["confidence"] * 100)
    quantity = decision_context["requested_quantity"]
    service_level_pct = round(decision_context["target_service_level"] * 100)

    if quantity > 0:
        sentences.append(
            f"The recommendation is to {position.lower()} an order of "
            f"{quantity} units of {product_name}, targeting a "
            f"{service_level_pct}% service level, with {confidence_pct}% "
            f"overall confidence."
        )
    else:
        sentences.append(
            f"The recommendation is {position.lower()} with no order needed "
            f"right now -- current stock already covers expected demand at "
            f"the {service_level_pct}% service level target, with "
            f"{confidence_pct}% overall confidence."
        )

    # --- Fold in the demand forecast, if available ---
    if forecast:
        trend_word = forecast.get("trend")
        avg_forecast = forecast.get("avg_forecasted_demand")
        if trend_word == "increasing":
            sentences.append(
                f"This is reinforced by the demand forecast, which projects "
                f"rising demand (averaging {avg_forecast} units/day over the "
                f"next {forecast.get('horizon_days')} days) -- understocking "
                f"now carries more risk than usual."
            )
        elif trend_word == "decreasing":
            sentences.append(
                f"Worth noting: the demand forecast projects declining "
                f"demand (averaging {avg_forecast} units/day over the next "
                f"{forecast.get('horizon_days')} days), which reduces the "
                f"urgency of a large order even if other departments flagged "
                f"concerns."
            )
        else:
            sentences.append(
                f"Demand is forecast to stay stable (around {avg_forecast} "
                f"units/day) over the next {forecast.get('horizon_days')} days, "
                f"so this decision is not being driven by an expected demand "
                f"shift."
            )

    # --- Fold in the trend diagnostic, if available and informative ---
    if trend_diagnostic and trend_diagnostic.get("available"):
        underlying = trend_diagnostic.get("underlying_trend_change_pct")
        verdict = trend_diagnostic.get("category_verdict")
        category = trend_diagnostic.get("category")

        if underlying is not None and abs(underlying) > 15:
            direction = "up" if underlying > 0 else "down"
            scope_note = ""
            if verdict == "category_wide":
                scope_note = (
                    f" and matches a broader move across the {category} "
                    f"category, not just this product"
                )
            elif verdict == "product_specific":
                scope_note = (
                    f", and appears specific to this product rather than "
                    f"the wider {category} category"
                )
            sentences.append(
                f"The underlying sales trend (seasonality removed) is "
                f"trending {direction} {abs(underlying)}%{scope_note} -- "
                f"worth factoring into how much confidence to place in this "
                f"recommendation."
            )

        significant_factors = [
            f for f in trend_diagnostic.get("correlated_factors", [])
            if f.get("significant")
        ]
        if significant_factors:
            factor_names = ", ".join(f["factor"].lower() for f in significant_factors)
            sentences.append(
                f"Note that {factor_names} {'is' if len(significant_factors) == 1 else 'are'} "
                f"statistically correlated with this product's demand -- "
                f"associated with the pattern, not confirmed as its cause."
            )

    return {
        "summary": " ".join(sentences),
        "based_on": {
            "department_votes": True,
            "demand_forecast": forecast is not None,
            "trend_diagnostic": bool(trend_diagnostic and trend_diagnostic.get("available")),
        },
    }
