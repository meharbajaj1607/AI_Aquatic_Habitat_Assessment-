# ============================================================
# AI AQUATIC HABITAT ASSESSMENT
# Train ML models to predict:
#   1. pH
#   2. Dissolved Oxygen (DO)
#
# Hardware inputs:
#   Temperature
#   TDS
#   Turbidity
#
# Dataset inputs:
#   Temperature
#   Specific Conductance
#   Turbidity
#
# IMPORTANT:
# Specific Conductance != TDS.
# We use a configurable conversion factor so that the
# hardware TDS can later be converted to equivalent
# specific conductance before prediction.
# ============================================================

import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

# ============================================================
# 1. FILE PATH
# ============================================================

DATASET_PATH = "SEAN_FQ_Q_2011-2024_KLGO_TA(2).csv"

# Folder where models will be saved
MODEL_FOLDER = "models"


# ============================================================
# 2. LOAD DATASET
# ============================================================

print("\nLoading dataset...")

df = pd.read_csv(DATASET_PATH, low_memory=False)

print("Original dataset shape:", df.shape)


# ============================================================
# 3. SELECT ONLY REQUIRED COLUMNS
# ============================================================

required_columns = [
    "water_temperature",
    "sp_conductance",
    "turbidity",
    "ph",
    "do_concentration"
]

df = df[required_columns].copy()

print("\nSelected columns:")
print(df.columns.tolist())


# ============================================================
# 4. CONVERT VALUES TO NUMERIC
# ============================================================

for column in required_columns:
    df[column] = pd.to_numeric(df[column], errors="coerce")


# ============================================================
# 5. REMOVE MISSING VALUES
# ============================================================

print("\nMissing values before cleaning:")
print(df.isnull().sum())

df = df.dropna()

print("\nRows after removing missing values:", len(df))


# ============================================================
# 6. REMOVE PHYSICALLY INVALID VALUES
# ============================================================

# Temperature
df = df[
    (df["water_temperature"] >= 0) &
    (df["water_temperature"] <= 40)
]

# Specific conductance
df = df[
    df["sp_conductance"] >= 0
]

# Turbidity
df = df[
    df["turbidity"] >= 0
]

# pH
df = df[
    (df["ph"] >= 0) &
    (df["ph"] <= 14)
]

# Dissolved oxygen
df = df[
    df["do_concentration"] >= 0
]

print("\nRows after physical filtering:", len(df))


# ============================================================
# 7. FEATURES AND TARGETS
# ============================================================

# These are the inputs corresponding to the hardware.
#
# Dataset currently has specific conductance rather than TDS.
#
# We keep the dataset variable as conductance because it is
# scientifically different from TDS.

X = df[
    [
        "water_temperature",
        "sp_conductance",
        "turbidity"
    ]
]

# Target 1
y_ph = df["ph"]

# Target 2
y_do = df["do_concentration"]


# ============================================================
# 8. TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_ph_train, y_ph_test = train_test_split(
    X,
    y_ph,
    test_size=0.20,
    random_state=42
)

# Use the SAME split for DO
_, _, y_do_train, y_do_test = train_test_split(
    X,
    y_do,
    test_size=0.20,
    random_state=42
)

print("\nTraining samples:", len(X_train))
print("Testing samples:", len(X_test))


# ============================================================
# 9. TRAIN pH MODEL
# ============================================================

print("\n========================================")
print("Training pH model...")
print("========================================")

ph_model = RandomForestRegressor(
    n_estimators=200,
    random_state=42,
    n_jobs=-1
)

ph_model.fit(X_train, y_ph_train)

ph_prediction = ph_model.predict(X_test)


# ============================================================
# 10. pH MODEL EVALUATION
# ============================================================

ph_mae = mean_absolute_error(
    y_ph_test,
    ph_prediction
)

ph_rmse = np.sqrt(
    mean_squared_error(
        y_ph_test,
        ph_prediction
    )
)

ph_r2 = r2_score(
    y_ph_test,
    ph_prediction
)

print("\n--- pH MODEL ---")
print(f"MAE  : {ph_mae:.4f}")
print(f"RMSE : {ph_rmse:.4f}")
print(f"R²   : {ph_r2:.4f}")


# ============================================================
# 11. TRAIN DO MODEL
# ============================================================

print("\n========================================")
print("Training Dissolved Oxygen model...")
print("========================================")

do_model = RandomForestRegressor(
    n_estimators=200,
    random_state=42,
    n_jobs=-1
)

do_model.fit(X_train, y_do_train)

do_prediction = do_model.predict(X_test)


# ============================================================
# 12. DO MODEL EVALUATION
# ============================================================

do_mae = mean_absolute_error(
    y_do_test,
    do_prediction
)

do_rmse = np.sqrt(
    mean_squared_error(
        y_do_test,
        do_prediction
    )
)

do_r2 = r2_score(
    y_do_test,
    do_prediction
)

print("\n--- DISSOLVED OXYGEN MODEL ---")
print(f"MAE  : {do_mae:.4f} mg/L")
print(f"RMSE : {do_rmse:.4f} mg/L")
print(f"R²   : {do_r2:.4f}")


# ============================================================
# 13. FEATURE IMPORTANCE
# ============================================================

feature_names = [
    "Temperature",
    "Specific Conductance",
    "Turbidity"
]

print("\n========================================")
print("pH FEATURE IMPORTANCE")
print("========================================")

for name, importance in zip(
    feature_names,
    ph_model.feature_importances_
):
    print(f"{name:25s}: {importance:.4f}")


print("\n========================================")
print("DO FEATURE IMPORTANCE")
print("========================================")

for name, importance in zip(
    feature_names,
    do_model.feature_importances_
):
    print(f"{name:25s}: {importance:.4f}")


# ============================================================
# 14. SAVE MODELS
# ============================================================

import os

os.makedirs(MODEL_FOLDER, exist_ok=True)

ph_model_path = os.path.join(
    MODEL_FOLDER,
    "ph_model.pkl"
)

do_model_path = os.path.join(
    MODEL_FOLDER,
    "do_model.pkl"
)

joblib.dump(
    ph_model,
    ph_model_path
)

joblib.dump(
    do_model,
    do_model_path
)

print("\n========================================")
print("MODELS SAVED")
print("========================================")

print("pH model :", ph_model_path)
print("DO model :", do_model_path)


# ============================================================
# 15. SAVE METRICS
# ============================================================

metrics = {
    "pH": {
        "MAE": float(ph_mae),
        "RMSE": float(ph_rmse),
        "R2": float(ph_r2)
    },

    "Dissolved Oxygen": {
        "MAE": float(do_mae),
        "RMSE": float(do_rmse),
        "R2": float(do_r2)
    }
}

metrics_path = os.path.join(
    MODEL_FOLDER,
    "model_metrics.json"
)

import json

with open(metrics_path, "w") as file:
    json.dump(metrics, file, indent=4)

print("Metrics :", metrics_path)

print("\nTraining completed successfully!")