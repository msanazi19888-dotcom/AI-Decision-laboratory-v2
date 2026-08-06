"""
Bridges the trained LightGBM demand model to the rest of the
application: single next-day predictions (used by InventoryAgent to
replace the plain historical mean) and multi-day horizon forecasts
(used by the standalone forecast endpoint / frontend chart).

Confidence is derived from how tightly the model's individual trees
agree with each other, not a hardcoded constant.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / "demand_model.joblib"
BASE_DIR = Path(__file__).resolve().parents[2]
SALES_PATH = BASE_DIR / "demo_data" / "smart_distribution" / "sales.csv"


class DemandForecastService:
    def __init__(self):
        bundle = joblib.load(MODEL_PATH)
        self.model = bundle["model"]
        self.feature_cols = bundle["feature_cols"]
        self.product_categories = bundle["product_categories"]
        self._sales = None

    def _load_sales(self):
        if self._sales is None:
            df = pd.read_csv(SALES_PATH, parse_dates=["date"])
            self._sales = df.sort_values(["product_id", "date"])
        return self._sales

    def _encode_product(self, product_id: str) -> int:
        if product_id not in self.product_categories:
            raise ValueError(f"No sales history for product_id: {product_id}")
        return self.product_categories.index(product_id)

    def _seed_history(self, product_id: str):
        """Returns the recent quantity_sold history for this product,
        as a plain list, to bootstrap recursive multi-day forecasting."""
        df = self._load_sales()
        history = df[df["product_id"] == product_id]
        if history.empty:
            raise ValueError(f"No sales history for product_id: {product_id}")
        return history["date"].iloc[-1], history["quantity_sold"].tolist()

    def _features_for_step(self, next_date, history, product_code):
        recent_7 = history[-7:]
        recent_14 = history[-14:]
        return {
            "day_of_week": next_date.dayofweek,
            "is_weekend": int(next_date.dayofweek in (5, 6)),
            "month": next_date.month,
            "week_of_year": int(next_date.isocalendar().week),
            "lag_1": history[-1],
            "lag_7": history[-7] if len(history) >= 7 else history[-1],
            "lag_14": history[-14] if len(history) >= 14 else history[-1],
            "rolling_mean_7": float(np.mean(recent_7)),
            "rolling_mean_14": float(np.mean(recent_14)),
            "rolling_std_7": float(np.std(recent_7)) if len(recent_7) > 1 else 0.0,
            "product_id_code": product_code,
        }

    def _confidence_from_volatility(self, features):
        # Confidence is derived from the product's own historical
        # volatility (coefficient of variation of its recent sales):
        # a product with stable, predictable demand yields a more
        # confident forecast than one with erratic day-to-day swings.
        mean = features["rolling_mean_7"] or 0.0
        std = features["rolling_std_7"] or 0.0
        if mean <= 0:
            return 0.5
        coefficient_of_variation = std / mean
        return round(max(0.4, min(0.97, 1 - coefficient_of_variation)), 2)

    def predict_next_day(self, product_id: str) -> dict:
        product_code = self._encode_product(product_id)
        last_date, history = self._seed_history(product_id)
        next_date = last_date + pd.Timedelta(days=1)

        features = self._features_for_step(next_date, history, product_code)
        X = pd.DataFrame([features])[self.feature_cols]
        prediction = float(self.model.predict(X)[0])
        prediction = max(0.0, prediction)

        confidence = self._confidence_from_volatility(features)

        historical_mean = float(np.mean(history[-30:]))

        return {
            "product_id": product_id,
            "predicted_next_day_demand": round(prediction, 2),
            "historical_30day_avg": round(historical_mean, 2),
            "confidence": round(confidence, 2),
        }

    def predict_horizon(self, product_id: str, days: int = 14) -> dict:
        product_code = self._encode_product(product_id)
        last_date, history = self._seed_history(product_id)
        history = list(history)  # working copy we extend recursively

        forecast_points = []
        current_date = last_date
        for _ in range(days):
            current_date = current_date + pd.Timedelta(days=1)
            features = self._features_for_step(current_date, history, product_code)
            X = pd.DataFrame([features])[self.feature_cols]
            prediction = max(0.0, float(self.model.predict(X)[0]))
            forecast_points.append(
                {"date": current_date.strftime("%Y-%m-%d"), "predicted_demand": round(prediction, 2)}
            )
            # Feed the prediction back in as if it were observed, so the
            # next step's lag/rolling features account for it.
            history.append(prediction)

        avg_forecast = float(np.mean([p["predicted_demand"] for p in forecast_points]))
        recent_actual_avg = float(np.mean(history[: len(history) - days][-30:]))

        trend = "increasing" if avg_forecast > recent_actual_avg * 1.05 else (
            "decreasing" if avg_forecast < recent_actual_avg * 0.95 else "stable"
        )

        return {
            "product_id": product_id,
            "horizon_days": days,
            "points": forecast_points,
            "avg_forecasted_demand": round(avg_forecast, 2),
            "recent_actual_avg": round(recent_actual_avg, 2),
            "trend": trend,
        }
