"""
readiness_score.py
Urban Flood Intelligence Engine
---------------------------------
Calculates a Pre-Monsoon Readiness Score (0–100) for each ward.

Score components (higher = better prepared):
  - Drainage maintenance score (35%)  : how recently drains were cleaned
  - Pump adequacy score (25%)         : pumps per km² of ward area
  - Drain density score (25%)         : drain length per km²
  - Historical resilience score (15%) : penalty for past flood events

Grade thresholds:
  A (80–100): Excellent — minimal intervention needed
  B (65–79) : Good — routine checks recommended
  C (50–64) : Fair — targeted improvements needed
  D (35–49) : Poor — urgent preventive action required
  F (0–34)  : Critical — immediate intervention mandatory
"""

from __future__ import annotations
import pandas as pd


# ── Tuning constants ──────────────────────────────────────────────────────────
MAX_CLEAN_DAYS        = 365   # days beyond which drain is considered neglected
IDEAL_PUMPS_PER_KM2   = 1.2   # target pump density
IDEAL_DRAIN_PER_KM2   = 4.0   # target drain-length density (km / km²)
MAX_FLOOD_EVENTS      = 5     # cap for normalisation

WEIGHTS = {
    "drainage_maintenance": 0.35,
    "pump_adequacy":        0.25,
    "drain_density":        0.25,
    "historical_resilience":0.15,
}


def _drainage_maintenance_score(days: float) -> float:
    """100 points if cleaned recently; drops to 0 at MAX_CLEAN_DAYS."""
    capped = min(days, MAX_CLEAN_DAYS)
    return max(0.0, 100.0 * (1 - capped / MAX_CLEAN_DAYS))


def _pump_adequacy_score(pump_count: float, area_km2: float) -> float:
    """100 points at or above IDEAL_PUMPS_PER_KM2."""
    if area_km2 <= 0:
        return 0.0
    density = pump_count / area_km2
    return min(100.0, 100.0 * density / IDEAL_PUMPS_PER_KM2)


def _drain_density_score(drain_km: float, area_km2: float) -> float:
    """100 points at or above IDEAL_DRAIN_PER_KM2."""
    if area_km2 <= 0:
        return 0.0
    density = drain_km / area_km2
    return min(100.0, 100.0 * density / IDEAL_DRAIN_PER_KM2)


def _historical_resilience_score(flood_events: float) -> float:
    """100 points for zero events; 0 points at MAX_FLOOD_EVENTS."""
    capped = min(flood_events, MAX_FLOOD_EVENTS)
    return max(0.0, 100.0 * (1 - capped / MAX_FLOOD_EVENTS))


def _grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "F"


def _recommendations(score: float, sub: dict[str, float], ward: str) -> list[str]:
    recs: list[str] = []

    if sub["drainage_maintenance"] < 50:
        recs.append("Schedule immediate drain cleaning — maintenance overdue.")
    if sub["pump_adequacy"] < 50:
        recs.append("Deploy additional pump units before monsoon onset.")
    if sub["drain_density"] < 50:
        recs.append("Expand drainage network coverage in underserved zones.")
    if sub["historical_resilience"] < 40:
        recs.append("Conduct community flood-preparedness drills (high past events).")
    if not recs:
        recs.append("Maintain current infrastructure standards; routine inspection advised.")
    return recs


def calculate_readiness(
    days_since_last_drain_clean: float,
    pump_count: float,
    area_km2: float,
    drain_length_km: float,
    historical_flood_events: float,
    ward: str = "",
) -> dict:
    """
    Calculate Pre-Monsoon Readiness Score for a single ward.

    Returns
    -------
    dict with keys:
        score           float   0–100
        grade           str     A / B / C / D / F
        sub_scores      dict    individual component scores
        recommendations list[str]
    """
    sub = {
        "drainage_maintenance": _drainage_maintenance_score(days_since_last_drain_clean),
        "pump_adequacy":        _pump_adequacy_score(pump_count, area_km2),
        "drain_density":        _drain_density_score(drain_length_km, area_km2),
        "historical_resilience":_historical_resilience_score(historical_flood_events),
    }

    total = sum(WEIGHTS[k] * v for k, v in sub.items())
    grade = _grade(total)

    return {
        "score":           round(total, 1),
        "grade":           grade,
        "sub_scores":      {k: round(v, 1) for k, v in sub.items()},
        "recommendations": _recommendations(total, sub, ward),
    }


def score_all_wards(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply calculate_readiness to every row in a DataFrame.
    Adds columns: readiness_score, readiness_grade.
    Returns the enriched DataFrame.
    """
    records = df.apply(
        lambda r: calculate_readiness(
            days_since_last_drain_clean=r["days_since_last_drain_clean"],
            pump_count=r["pump_count"],
            area_km2=r["area_km2"],
            drain_length_km=r["drain_length_km"],
            historical_flood_events=r["historical_flood_events"],
            ward=r.get("location", ""),
        ),
        axis=1,
        result_type="expand",
    )
    df = df.copy()
    df["readiness_score"] = records["score"]
    df["readiness_grade"] = records["grade"]
    df["recommendations"] = records["recommendations"]
    df["sub_scores"]      = records["sub_scores"]
    return df


# ── Demo ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flood_risk import calculate_flood_risk

    csv_path = os.path.join(os.path.dirname(__file__), "flood_data.csv")
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip().str.lower()
    df = score_all_wards(df)

    df["flood_risk"] = df.apply(
        lambda r: calculate_flood_risk(r["rainfall_mm_hr"], r["elevation_m"], r["drainage_capacity_mm_hr"]),
        axis=1,
    )

    print(f"\n{'Ward':<22} {'Risk':<10} {'Score':>6} {'Grade':>5}")
    print("─" * 50)
    for _, row in df.sort_values("readiness_score").iterrows():
        print(f"{row['location']:<22} {row['flood_risk']:<10} {row['readiness_score']:>6.1f} {row['readiness_grade']:>5}")

    grade_counts = df["readiness_grade"].value_counts().sort_index()
    print(f"\nGrade distribution: {grade_counts.to_dict()}")
    avg = df["readiness_score"].mean()
    print(f"City avg readiness: {avg:.1f}")
