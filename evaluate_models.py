"""
=============================================================
AI AQUATIC HABITAT ASSESSMENT
Reproducible Machine Learning Model Evaluation Script
=============================================================

This script independently evaluates the trained Gradient Boosting
regression models for pH and Dissolved Oxygen (DO) against the
chronological held-out test split of the USGS/NPS KLGO water quality dataset.

Dataset: Taiya River (KLGO), Southeast Alaska Network (2011–2024)
Training Period: 2011-04-25 to 2022-07-31
Testing Period:  2022-07-31 to 2024-10-24

Metrics Calculated:
  - Mean Absolute Error (MAE)
  - Root Mean Squared Error (RMSE)
  - Coefficient of Determination (R²)
=============================================================
"""

import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Ensure clean UTF-8 console output on Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATASET_PATH = os.path.join(SCRIPT_DIR, "SEAN_FQ_Q_2011-2024_KLGO_TA.csv")
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")

PH_MODEL_PATH = os.path.join(MODELS_DIR, "final_ph_gradient_boosting.pkl")
DO_MODEL_PATH = os.path.join(MODELS_DIR, "final_do_gradient_boosting.pkl")


def evaluate_models():
    print("\n" + "=" * 65)
    print("  AI AQUATIC HABITAT ASSESSMENT - ML MODEL REPRODUCIBILITY EVALUATION")
    print("=" * 65)

    # 1. Dataset Verification
    if not os.path.exists(DATASET_PATH):
        print(f"[ERROR] Dataset file not found at: {DATASET_PATH}")
        sys.exit(1)

    print(f"\n1. Loading dataset: {os.path.basename(DATASET_PATH)}...")
    df = pd.read_csv(DATASET_PATH, low_memory=False)
    original_count = len(df)
    print(f"   Total records in raw CSV: {original_count:,}")

    # 2. Preprocessing & Physical Filters
    features = ["water_temperature", "sp_conductance", "turbidity"]
    targets = ["ph", "do_concentration"]

    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], errors="coerce", utc=True)
    for col in features + targets:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["timestamp_utc"] + features + targets)

    # Apply physical bounds from training pipeline
    df = df[
        (df["water_temperature"] >= 0) & (df["water_temperature"] <= 40) &
        (df["sp_conductance"] >= 0) &
        (df["turbidity"] >= 0) &
        (df["ph"] >= 0) & (df["ph"] <= 14) &
        (df["do_concentration"] >= 0)
    ].copy()

    df = df.sort_values("timestamp_utc")
    cleaned_count = len(df)
    print(f"   Cleaned records after physical filtering: {cleaned_count:,}")

    # 3. Chronological Train/Test Split
    split_timestamp = pd.to_datetime("2022-07-31 17:00:00+00:00")
    train_df = df[df["timestamp_utc"] <= split_timestamp]
    test_df = df[df["timestamp_utc"] > split_timestamp]

    print(f"\n2. Chronological Split (Cutoff: {split_timestamp}):")
    print(f"   Training partition: {len(train_df):,} samples ({train_df['timestamp_utc'].min().date()} to {train_df['timestamp_utc'].max().date()})")
    print(f"   Testing partition:  {len(test_df):,} samples ({test_df['timestamp_utc'].min().date()} to {test_df['timestamp_utc'].max().date()})")

    # 4. Load Models
    print("\n3. Deserializing model artifacts...")
    if not os.path.exists(PH_MODEL_PATH) or not os.path.exists(DO_MODEL_PATH):
        print("[ERROR] Model files missing from models/ directory.")
        sys.exit(1)

    ph_model = joblib.load(PH_MODEL_PATH)
    do_model = joblib.load(DO_MODEL_PATH)

    print(f"   pH Model loaded: {os.path.basename(PH_MODEL_PATH)}")
    print(f"   DO Model loaded: {os.path.basename(DO_MODEL_PATH)}")

    # 5. Model Evaluation
    X_test = test_df[features]
    y_ph_test = test_df["ph"]
    y_do_test = test_df["do_concentration"]

    ph_pred = ph_model.predict(X_test)
    do_pred = do_model.predict(X_test)

    ph_mae = mean_absolute_error(y_ph_test, ph_pred)
    ph_rmse = np.sqrt(mean_squared_error(y_ph_test, ph_pred))
    ph_r2 = r2_score(y_ph_test, ph_pred)

    do_mae = mean_absolute_error(y_do_test, do_pred)
    do_rmse = np.sqrt(mean_squared_error(y_do_test, do_pred))
    do_r2 = r2_score(y_do_test, do_pred)

    print("\n" + "=" * 65)
    print("  MODEL EVALUATION RESULTS (ON HELD-OUT CHRONOLOGICAL TEST SET)")
    print("=" * 65)
    print("\n  Target: pH (Gradient Boosting Regressor)")
    print(f"    MAE  : {ph_mae:.4f}")
    print(f"    RMSE : {ph_rmse:.4f}")
    print(f"    R2   : {ph_r2:.4f}")

    print("\n  Target: Dissolved Oxygen (Gradient Boosting Regressor)")
    print(f"    MAE  : {do_mae:.4f} mg/L")
    print(f"    RMSE : {do_rmse:.4f} mg/L")
    print(f"    R2   : {do_r2:.4f}")

    # Feature importances
    print("\n" + "-" * 65)
    print("  FEATURE IMPORTANCES")
    print("-" * 65)
    for feat, imp in zip(features, ph_model.feature_importances_):
        print(f"    pH Model  - {feat:20s}: {imp * 100:6.2f}%")
    print()
    for feat, imp in zip(features, do_model.feature_importances_):
        print(f"    DO Model  - {feat:20s}: {imp * 100:6.2f}%")

    # Domain shift check
    print("\n" + "-" * 65)
    print("  TRAINING DISTRIBUTION PROFILE (TAIYA RIVER, ALASKA)")
    print("-" * 65)
    for feat in features:
        print(f"    {feat:20s}: Min={train_df[feat].min():.2f}, Mean={train_df[feat].mean():.2f}, Max={train_df[feat].max():.2f}")

    print("\n[NOTE] Training dataset water temperature max is 12.97°C.")
    print("       Evaluating on warm tropical waters (>20°C) is an out-of-distribution regime.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    evaluate_models()
