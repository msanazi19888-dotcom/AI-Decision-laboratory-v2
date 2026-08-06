"""
Trains a per-product demand forecasting model on the real DataCo-derived
sales history (app/demo_data/smart_distribution/sales.csv).

Uses lag/rolling features + calendar features, LightGBM, and a
TIME-BASED train/test split (never a random split for time series --
that leaks adjacent days into training via the rolling-window features
and produces artificially good accuracy).
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

BASE_DIR = Path(__file__).resolve().parents[2]
SALES_PATH = BASE_DIR / "demo_data" / "smart_distribution" / "sales.csv"
MODEL_PATH = Path(__file__).resolve().parent / "demand_model.joblib"

FEATURE_COLS = [
    "day_of_week", "is_weekend", "month", "week_of_year",
    "lag_1", "lag_7", "lag_14",
    "rolling_mean_7", "rolling_mean_14", "rolling_std_7",
    "product_id_code",
]
TARGET = "quantity_sold"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["product_id", "date"]).copy()

    df["day_of_week"] = df["date"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["month"] = df["date"].dt.month
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)

    grp = df.groupby("product_id")[TARGET]
    df["lag_1"] = grp.shift(1)
    df["lag_7"] = grp.shift(7)
    df["lag_14"] = grp.shift(14)
    df["rolling_mean_7"] = df.groupby("product_id")[TARGET].transform(
        lambda x: x.shift(1).rolling(7).mean()
    )
    df["rolling_mean_14"] = df.groupby("product_id")[TARGET].transform(
        lambda x: x.shift(1).rolling(14).mean()
    )
    df["rolling_std_7"] = df.groupby("product_id")[TARGET].transform(
        lambda x: x.shift(1).rolling(7).std()
    )

    df["product_id"] = df["product_id"].astype("category")
    df["product_id_code"] = df["product_id"].cat.codes

    df = df.dropna(subset=["lag_1", "lag_7", "lag_14", "rolling_mean_7", "rolling_mean_14"])
    return df


def train():
    raw = pd.read_csv(SALES_PATH, parse_dates=["date"])
    df = build_features(raw)

    cutoff = df["date"].max() - pd.Timedelta(days=30)
    train_df = df[df["date"] <= cutoff]
    test_df = df[df["date"] > cutoff]

    X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET]
    X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET]

    model = lgb.LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        max_depth=8,
        min_child_samples=10,
        random_state=42,
        verbosity=-1,
    )
    model.fit(X_train, y_train)

    preds = np.clip(model.predict(X_test), 0, None)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))

    # naive baseline for comparison: predict lag_7 (same weekday last week)
    baseline_preds = test_df["lag_7"].fillna(test_df["lag_1"])
    baseline_mae = mean_absolute_error(y_test, baseline_preds)

    print(f"Train rows: {len(train_df):,} | Test rows: {len(test_df):,}")
    print(f"Naive baseline MAE: {baseline_mae:.2f}")
    print(f"LightGBM MAE:       {mae:.2f}")
    print(f"LightGBM RMSE:      {rmse:.2f}")

    # Save the product_id category mapping alongside the model so
    # inference can encode new requests consistently.
    product_categories = df["product_id"].cat.categories.tolist()

    joblib.dump(
        {"model": model, "feature_cols": FEATURE_COLS, "product_categories": product_categories},
        MODEL_PATH,
    )
    print(f"Saved model -> {MODEL_PATH}")


if __name__ == "__main__":
    train()
