"""
app.py
Urban Flood Intelligence Engine — Flask API + Dashboard
--------------------------------------------------------
Endpoints
---------
GET  /                            Health check
GET  /dashboard                   Interactive web dashboard
GET  /api/predictions             All CSV predictions (legacy)
GET  /api/predictions/<location>  Single-location lookup (legacy)
POST /api/predict                 Ad-hoc rule-based prediction
GET  /api/summary                 Aggregate counts per risk level
GET  /api/wards                   All 25 wards with risk + readiness
GET  /api/wards/<ward_id>         Full detail for one ward
GET  /api/readiness-summary       City-level readiness aggregates
POST /api/ml/predict              ML-based prediction from JSON body
"""

import os
import pandas as pd
from flask import Flask, jsonify, request, abort, render_template

from flood_risk import calculate_flood_risk
from readiness_score import score_all_wards, calculate_readiness

# ── App setup ──────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CSV_PATH   = os.path.join(BASE_DIR, "flood_data.csv")

app = Flask(__name__, template_folder="templates", static_folder="static")

REQUIRED_BASE = {"location", "rainfall_mm_hr", "elevation_m", "drainage_capacity_mm_hr"}
WARD_COLS     = {"ward_id", "population", "area_km2", "drain_length_km",
                 "pump_count", "days_since_last_drain_clean", "historical_flood_events"}


# ── Data helpers ────────────────────────────────────────────────────────────────

def _load_csv() -> pd.DataFrame:
    if not os.path.exists(CSV_PATH):
        abort(500, description=f"Data file not found: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    df.columns = df.columns.str.strip().str.lower()
    missing = REQUIRED_BASE - set(df.columns)
    if missing:
        abort(500, description=f"CSV missing columns: {missing}")
    for col in ("rainfall_mm_hr", "elevation_m", "drainage_capacity_mm_hr"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _load_ward_csv() -> pd.DataFrame:
    df = _load_csv()
    all_cols = REQUIRED_BASE | WARD_COLS | {"latitude", "longitude"}
    numeric_cols = all_cols - {"location", "ward_id"}   # keep ward_id as string
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["ward_id"] = df["ward_id"].astype(str)
    df["flood_risk"] = df.apply(
        lambda r: calculate_flood_risk(r["rainfall_mm_hr"], r["elevation_m"], r["drainage_capacity_mm_hr"]),
        axis=1,
    )
    df = score_all_wards(df)
    return df



def _row_to_pred(row: pd.Series) -> dict:
    risk = calculate_flood_risk(
        float(row["rainfall_mm_hr"]),
        float(row["elevation_m"]),
        float(row["drainage_capacity_mm_hr"]),
    )
    return {
        "location":   row["location"],
        "inputs": {
            "rainfall_mm_hr":          float(row["rainfall_mm_hr"]),
            "elevation_m":             float(row["elevation_m"]),
            "drainage_capacity_mm_hr": float(row["drainage_capacity_mm_hr"]),
        },
        "flood_risk": risk,
    }


def _ward_to_dict(row: pd.Series) -> dict:
    return {
        "ward_id":          row.get("ward_id", ""),
        "location":         row["location"],
        "coordinates":      {"lat": float(row.get("latitude", 0)),
                             "lon": float(row.get("longitude", 0))},
        "population":       int(row.get("population", 0)),
        "area_km2":         float(row.get("area_km2", 0)),
        "infrastructure": {
            "drain_length_km":            float(row.get("drain_length_km", 0)),
            "pump_count":                 int(row.get("pump_count", 0)),
            "days_since_last_drain_clean":int(row.get("days_since_last_drain_clean", 0)),
            "historical_flood_events":    int(row.get("historical_flood_events", 0)),
        },
        "inputs": {
            "rainfall_mm_hr":          float(row["rainfall_mm_hr"]),
            "elevation_m":             float(row["elevation_m"]),
            "drainage_capacity_mm_hr": float(row["drainage_capacity_mm_hr"]),
        },
        "flood_risk":       row.get("flood_risk", ""),
        "readiness_score":  float(row.get("readiness_score", 0)),
        "readiness_grade":  row.get("readiness_grade", ""),
        "recommendations":  row.get("recommendations", []),
        "sub_scores":       row.get("sub_scores", {}),
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return jsonify({"status": "ok", "service": "Urban Flood Intelligence Engine", "version": "2.0.0"})


@app.get("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ── Legacy prediction endpoints ─────────────────────────────────────────────────

@app.get("/api/predictions")
def all_predictions():
    df      = _load_csv()
    results = [_row_to_pred(row) for _, row in df.iterrows()]
    rf      = request.args.get("risk", "").strip().capitalize()
    if rf:
        if rf not in ("Low", "Moderate", "High"):
            abort(400, description="risk param must be one of: Low, Moderate, High")
        results = [r for r in results if r["flood_risk"] == rf]
    return jsonify({"count": len(results), "predictions": results})


@app.get("/api/predictions/<string:location>")
def single_prediction(location: str):
    df    = _load_csv()
    match = df[df["location"].str.lower() == location.lower()]
    if match.empty:
        abort(404, description=f"Location '{location}' not found.")
    return jsonify(_row_to_pred(match.iloc[0]))


@app.post("/api/predict")
def ad_hoc_predict():
    data = request.get_json(silent=True)
    if not data:
        abort(400, description="Request body must be valid JSON.")
    required = ("rainfall_mm_hr", "elevation_m", "drainage_capacity_mm_hr")
    missing  = [k for k in required if k not in data]
    if missing:
        abort(400, description=f"Missing fields: {missing}")
    try:
        rain, elev, drain = float(data["rainfall_mm_hr"]), float(data["elevation_m"]), float(data["drainage_capacity_mm_hr"])
    except (TypeError, ValueError) as exc:
        abort(400, description=f"Numeric fields required. {exc}")
    try:
        risk = calculate_flood_risk(rain, elev, drain)
    except ValueError as exc:
        abort(400, description=str(exc))
    return jsonify({
        "location":   data.get("location", "Custom"),
        "inputs":     {"rainfall_mm_hr": rain, "elevation_m": elev, "drainage_capacity_mm_hr": drain},
        "flood_risk": risk,
    }), 201


@app.get("/api/summary")
def summary():
    df      = _load_csv()
    results = [_row_to_pred(row) for _, row in df.iterrows()]
    bkd: dict[str, list] = {"High": [], "Moderate": [], "Low": []}
    for r in results:
        bkd[r["flood_risk"]].append(r["location"])
    return jsonify({
        "total_locations": len(results),
        "summary": {lvl: {"count": len(locs), "locations": locs} for lvl, locs in bkd.items()},
    })


# ── Ward endpoints ──────────────────────────────────────────────────────────────

@app.get("/api/wards")
def all_wards():
    df      = _load_ward_csv()
    rf      = request.args.get("risk", "").strip().capitalize()
    grade   = request.args.get("grade", "").strip().upper()
    sort_by = request.args.get("sort", "readiness_score")

    wards = [_ward_to_dict(row) for _, row in df.iterrows()]

    if rf:
        if rf not in ("Low", "Moderate", "High"):
            abort(400, description="risk must be Low, Moderate, or High")
        wards = [w for w in wards if w["flood_risk"] == rf]
    if grade:
        if grade not in ("A", "B", "C", "D", "F"):
            abort(400, description="grade must be one of A B C D F")
        wards = [w for w in wards if w["readiness_grade"] == grade]

    # Sort
    reverse = sort_by.startswith("-")
    key     = sort_by.lstrip("-")
    if key in ("readiness_score", "population", "area_km2"):
        wards.sort(key=lambda w: w.get(key, 0), reverse=reverse)

    return jsonify({"count": len(wards), "wards": wards})


@app.get("/api/wards/<string:ward_id>")
def single_ward(ward_id: str):
    df = _load_ward_csv()
    df["ward_id"] = df["ward_id"].astype(str)
    match = df[df["ward_id"].str.upper() == ward_id.upper()]
    if match.empty:
        # fall back to location name search
        match = df[df["location"].str.lower() == ward_id.lower()]
    if match.empty:
        abort(404, description=f"Ward '{ward_id}' not found.")
    return jsonify(_ward_to_dict(match.iloc[0]))



@app.get("/api/readiness-summary")
def readiness_summary():
    df     = _load_ward_csv()
    grades = df["readiness_grade"].value_counts().to_dict()
    risks  = df["flood_risk"].value_counts().to_dict()

    critical = df[df["readiness_grade"].isin(["D", "F"])].sort_values("readiness_score")
    top_action = [
        {"ward_id": r["ward_id"], "location": r["location"],
         "readiness_score": round(r["readiness_score"], 1),
         "readiness_grade": r["readiness_grade"],
         "flood_risk": r["flood_risk"],
         "top_recommendation": r["recommendations"][0] if r["recommendations"] else ""}
        for _, r in critical.head(5).iterrows()
    ]

    return jsonify({
        "total_wards":      len(df),
        "avg_readiness":    round(df["readiness_score"].mean(), 1),
        "min_readiness":    round(df["readiness_score"].min(), 1),
        "max_readiness":    round(df["readiness_score"].max(), 1),
        "grade_breakdown":  {g: int(grades.get(g, 0)) for g in ("A", "B", "C", "D", "F")},
        "risk_breakdown":   {r: int(risks.get(r, 0)) for r in ("High", "Moderate", "Low")},
        "top_action_wards": top_action,
    })


@app.post("/api/ml/predict")
def ml_predict():
    try:
        from ml_model import predict as ml_pred, FEATURES
    except ImportError:
        abort(500, description="ML module unavailable.")

    data = request.get_json(silent=True)
    if not data:
        abort(400, description="JSON body required.")
    missing = [f for f in FEATURES if f not in data]
    if missing:
        abort(400, description=f"Missing ML features: {missing}")
    try:
        features = {f: float(data[f]) for f in FEATURES}
    except (TypeError, ValueError) as exc:
        abort(400, description=f"All features must be numeric. {exc}")

    result = ml_pred(features)
    return jsonify({
        "location":       data.get("location", "Custom"),
        "inputs":         features,
        "ml_prediction":  result,
        "rule_based":     calculate_flood_risk(
            features["rainfall_mm_hr"],
            features["elevation_m"],
            features["drainage_capacity_mm_hr"],
        ),
    }), 201


# ── Error handlers ──────────────────────────────────────────────────────────────

@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(500)
def handle_error(exc):
    return jsonify({"error": exc.description}), exc.code


# ── Entry point ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
