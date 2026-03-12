"""
flood_risk.py
Urban Flood Intelligence Engine
--------------------------------
Calculates flood risk level based on:
  - Rainfall             (mm / hour)
  - Terrain Elevation    (metres above sea level)
  - Drainage Capacity    (mm / hour the drainage system can handle)

Returns: "Low", "Moderate", or "High"
"""

from __future__ import annotations


def calculate_flood_risk(
    rainfall_mm_hr: float,
    elevation_m: float,
    drainage_capacity_mm_hr: float,
) -> str:
    """
    Calculate the flood risk level for an urban area.

    Parameters
    ----------
    rainfall_mm_hr : float
        Current or forecasted rainfall intensity in mm per hour.
        Typical ranges:
            < 10   → light rain
            10–50  → moderate rain
            > 50   → heavy / extreme rain
    elevation_m : float
        Terrain elevation in metres above sea level.
        Lower elevations accumulate water faster.
        Typical urban ranges: 0–500 m (lowlands vs. hillside).
    drainage_capacity_mm_hr : float
        How many mm of rain per hour the local drainage system
        can safely discharge.  Values closer to 0 mean poor drainage.

    Returns
    -------
    str
        One of "Low", "Moderate", or "High".

    Raises
    ------
    ValueError
        If any parameter is negative.

    Examples
    --------
    >>> calculate_flood_risk(5, 120, 30)
    'Low'
    >>> calculate_flood_risk(35, 15, 20)
    'High'
    >>> calculate_flood_risk(20, 60, 25)
    'Moderate'
    """
    # ── Input validation ────────────────────────────────────────────────────
    if rainfall_mm_hr < 0:
        raise ValueError(f"rainfall_mm_hr must be >= 0, got {rainfall_mm_hr}")
    if elevation_m < 0:
        raise ValueError(f"elevation_m must be >= 0, got {elevation_m}")
    if drainage_capacity_mm_hr < 0:
        raise ValueError(f"drainage_capacity_mm_hr must be >= 0, got {drainage_capacity_mm_hr}")

    # ── Factor 1: Rainfall score (0–40 pts) ─────────────────────────────────
    # Light < 10, moderate 10–30, heavy 30–60, extreme > 60 mm/hr
    if rainfall_mm_hr < 10:
        rainfall_score = 0
    elif rainfall_mm_hr < 30:
        rainfall_score = 15
    elif rainfall_mm_hr < 60:
        rainfall_score = 30
    else:
        rainfall_score = 40

    # ── Factor 2: Elevation score (0–30 pts) ────────────────────────────────
    # Lower ground = more accumulation risk
    if elevation_m >= 100:
        elevation_score = 0
    elif elevation_m >= 50:
        elevation_score = 10
    elif elevation_m >= 20:
        elevation_score = 20
    else:
        elevation_score = 30

    # ── Factor 3: Drainage deficit score (0–30 pts) ─────────────────────────
    # How much rainfall EXCEEDS drainage capacity
    drainage_deficit = max(0.0, rainfall_mm_hr - drainage_capacity_mm_hr)

    if drainage_deficit == 0:
        drainage_score = 0
    elif drainage_deficit < 10:
        drainage_score = 10
    elif drainage_deficit < 30:
        drainage_score = 20
    else:
        drainage_score = 30

    # ── Composite risk score (0–100) ─────────────────────────────────────────
    total_score = rainfall_score + elevation_score + drainage_score

    # ── Classification ───────────────────────────────────────────────────────
    if total_score < 30:
        return "Low"
    elif total_score < 60:
        return "Moderate"
    else:
        return "High"


# ── Quick demo ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    scenarios = [
        # (rainfall, elevation, drainage, label)
        (5,   120, 30, "Light rain, high ground, good drainage"),
        (20,   60, 25, "Moderate rain, moderate elevation, adequate drainage"),
        (35,   15, 20, "Heavy rain, low-lying area, limited drainage"),
        (70,    5, 10, "Extreme rain, near sea level, overwhelmed drainage"),
        (15,   80, 5,  "Moderate rain, highland but very poor drainage"),
    ]

    header = f"{'Scenario':<48} {'Score Inputs':^35} {'Risk'}"
    print(header)
    print("─" * len(header))

    for rain, elev, drain, desc in scenarios:
        risk = calculate_flood_risk(rain, elev, drain)
        print(f"{desc:<48}  rain={rain:>3} mm/hr  elev={elev:>4} m  drain={drain:>2} mm/hr  →  {risk}")
