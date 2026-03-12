"""
ml_model.py
Urban Flood Intelligence Engine
---------------------------------
Trains a Random Forest classifier to predict flood risk (Low / Moderate / High).

Features used
-------------
  rainfall_mm_hr, elevation_m, drainage_capacity_mm_hr,
  days_since_last_drain_clean, pump_count, historical_flood_events,
  area_km2, drain_length_km

Label
-----
  flood_risk — derived from calculate_flood_risk()

Outputs
-------
  flood_model.pkl   — trained model (via joblib)
  flood_encoder.pkl — LabelEncoder for the target class

Usage
-----
  python3 ml_model.py          # trains and saves model
  from ml_model import predict  # for inference
"""

from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import classification_report, accuracy_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flood_risk import calculate_flood_risk

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CSV_PATH    = os.path.join(BASE_DIR, "flood_data.csv")
MODEL_PATH  = os.path.join(BASE_DIR, "flood_model.pkl")
ENCODER_PATH = os.path.join(BASE_DIR, "flood_encoder.pkl")

FEATURES = [
    "rainfall_mm_hr",
    "elevation_m",
    "drainage_capacity_mm_hr",
    "days_since_last_drain_clean",
    "pump_count",
    "historical_flood_events",
    "area_km2",
    "drain_length_km",
]


# ── Synthetic augmentation ─────────────────────────────────────────────────────
def _augment(df: pd.DataFrame, n: int = 800, seed: int = 42) -> pd.DataFrame:
    """
    Synthetic data generation by perturbing real records.
    Ensures enough samples for robust cross-validation.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        base = df.sample(1, random_state=int(rng.integers(0, 10_000))).iloc[0]
        perturbed = {
            "rainfall_mm_hr":             max(0, base["rainfall_mm_hr"]            + rng.normal(0, 8)),
            "elevation_m":                max(0, base["elevation_m"]               + rng.normal(0, 10)),
            "drainage_capacity_mm_hr":    max(1, base["drainage_capacity_mm_hr"]   + rng.normal(0, 4)),
            "days_since_last_drain_clean":max(0, base["days_since_last_drain_clean"]+ rng.normal(0, 20)),
            "pump_count":                 max(0, round(base["pump_count"]          + rng.normal(0, 1))),
            "historical_flood_events":    int(np.clip(base["historical_flood_events"] + rng.integers(-1, 2), 0, 8)),
            "area_km2":                   max(1, base["area_km2"]                  + rng.normal(0, 1)),
            "drain_length_km":            max(1, base["drain_length_km"]           + rng.normal(0, 3)),
        }
        perturbed["flood_risk"] = calculate_flood_risk(
            perturbed["rainfall_mm_hr"],
            perturbed["elevation_m"],
            perturbed["drainage_capacity_mm_hr"],
        )
        rows.append(perturbed)
    return pd.DataFrame(rows)


# ── Training ───────────────────────────────────────────────────────────────────
def train(verbose: bool = True) -> tuple[RandomForestClassifier, LabelEncoder]:
    df = pd.read_csv(CSV_PATH)
    df.columns = df.columns.str.strip().str.lower()

    df["flood_risk"] = df.apply(
        lambda r: calculate_flood_risk(r["rainfall_mm_hr"], r["elevation_m"], r["drainage_capacity_mm_hr"]),
        axis=1,
    )

    augmented = _augment(df)
    full_df = pd.concat([df[FEATURES + ["flood_risk"]], augmented], ignore_index=True)

    le = LabelEncoder()
    y = le.fit_transform(full_df["flood_risk"])
    X = full_df[FEATURES].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    if verbose:
        y_pred = model.predict(X_test)
        print(f"Test accuracy : {accuracy_score(y_test, y_pred):.3f}")
        print("\nClassification report:")
        print(classification_report(y_test, y_pred, target_names=le.classes_))

        cv_scores = cross_val_score(model, X, y, cv=StratifiedKFold(5), scoring="accuracy")
        print(f"5-fold CV accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

        importances = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
        print("\nFeature importances:")
        for feat, imp in importances.items():
            bar = "█" * int(imp * 40)
            print(f"  {feat:<30} {bar} {imp:.3f}")

    joblib.dump(model, MODEL_PATH)
    joblib.dump(le, ENCODER_PATH)
    if verbose:
        print(f"\nModel saved → {MODEL_PATH}")
        print(f"Encoder saved → {ENCODER_PATH}")

    return model, le


# ── Inference ──────────────────────────────────────────────────────────────────
def _load() -> tuple:
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Model not found. Run `python3 ml_model.py` first.")
    return joblib.load(MODEL_PATH), joblib.load(ENCODER_PATH)


def predict(features: dict) -> dict:
    """
    Predict flood risk for a single location.

    Parameters
    ----------
    features : dict  — keys matching FEATURES list (all numeric)

    Returns
    -------
    dict:
        risk        str     Low / Moderate / High
        probability float   confidence for the predicted class (0–1)
        all_probs   dict    probabilities for each class
    """
    model, le = _load()

    row = np.array([[features[f] for f in FEATURES]])
    idx  = model.predict(row)[0]
    probs = model.predict_proba(row)[0]

    all_probs = {cls: round(float(p), 4) for cls, p in zip(le.classes_, probs)}
    risk = le.inverse_transform([idx])[0]

    return {
        "risk":        risk,
        "probability": round(float(probs[idx]), 4),
        "all_probs":   all_probs,
    }


def predict_all_wards(df: pd.DataFrame) -> pd.DataFrame:
    """
    Batch-predict for an entire ward DataFrame.
    Adds columns: ml_risk, ml_probability.
    """
    model, le = _load()
    X = df[FEATURES].values
    idxs  = model.predict(X)
    probs = model.predict_proba(X)

    df = df.copy()
    df["ml_risk"]        = le.inverse_transform(idxs)
    df["ml_probability"] = [round(float(p[i]), 4) for i, p in zip(idxs, probs)]
    return df


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print(" Urban Flood Intelligence Engine — ML Model Training")
    print("=" * 60)
    model, le = train(verbose=True)

    print("\n── Sample inference ──")
    sample = {
        "rainfall_mm_hr": 65,
        "elevation_m": 8,
        "drainage_capacity_mm_hr": 12,
        "days_since_last_drain_clean": 142,
        "pump_count": 6,
        "historical_flood_events": 4,
        "area_km2": 4.2,
        "drain_length_km": 18.5,
    }
    result = predict(sample)
    print(f"Input: {sample}")
    print(f"Predicted: {result['risk']} (confidence: {result['probability']:.1%})")
    print(f"All probs: {result['all_probs']}")
