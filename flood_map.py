"""
flood_map.py
Urban Flood Intelligence Engine
---------------------------------
Reads flood_data.csv, calculates flood risk for every location using
calculate_flood_risk(), then renders an interactive Folium map with
colour-coded circle markers and saves it to flood_map.html.

Marker colours
--------------
  High     → red
  Moderate → orange
  Low      → green
"""

import os
import webbrowser

import folium
import pandas as pd

from flood_risk import calculate_flood_risk

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH  = os.path.join(BASE_DIR, "flood_data.csv")
HTML_PATH = os.path.join(BASE_DIR, "flood_map.html")

# ── Colour mapping ─────────────────────────────────────────────────────────────
RISK_COLOUR: dict[str, str] = {
    "High":     "red",
    "Moderate": "orange",
    "Low":      "green",
}

RISK_ICON: dict[str, str] = {
    "High":     "exclamation-triangle",
    "Moderate": "exclamation-circle",
    "Low":      "check-circle",
}


def load_data(path: str) -> pd.DataFrame:
    """Load and validate the CSV, then calculate risk for every row."""
    required = {"location", "rainfall_mm_hr", "elevation_m",
                "drainage_capacity_mm_hr", "latitude", "longitude"}

    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower()

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    for col in ("rainfall_mm_hr", "elevation_m",
                "drainage_capacity_mm_hr", "latitude", "longitude"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[list(required - {"location"})].isnull().any().any():
        raise ValueError("CSV contains non-numeric or missing values in numeric columns.")

    df["flood_risk"] = df.apply(
        lambda r: calculate_flood_risk(
            rainfall_mm_hr=r["rainfall_mm_hr"],
            elevation_m=r["elevation_m"],
            drainage_capacity_mm_hr=r["drainage_capacity_mm_hr"],
        ),
        axis=1,
    )
    return df


def build_map(df: pd.DataFrame) -> folium.Map:
    """Construct a Folium map with colour-coded markers and a legend."""

    # Centre the map on the dataset centroid
    centre_lat = df["latitude"].mean()
    centre_lon = df["longitude"].mean()

    fmap = folium.Map(
        location=[centre_lat, centre_lon],
        zoom_start=11,
        tiles="CartoDB positron",
    )

    # ── Marker cluster layer groups (one per risk level) ──────────────────────
    groups = {level: folium.FeatureGroup(name=f"{level} Risk", show=True)
              for level in ("High", "Moderate", "Low")}

    for _, row in df.iterrows():
        risk  = row["flood_risk"]
        color = RISK_COLOUR[risk]
        icon  = RISK_ICON[risk]

        # Rich popup HTML
        popup_html = f"""
        <div style="font-family:Arial,sans-serif;min-width:200px;">
            <h4 style="margin:0 0 6px;color:#333;">{row['location']}</h4>
            <hr style="margin:4px 0;">
            <table style="width:100%;font-size:13px;">
                <tr><td>🌧 Rainfall</td>
                    <td><b>{row['rainfall_mm_hr']} mm/hr</b></td></tr>
                <tr><td>⛰ Elevation</td>
                    <td><b>{row['elevation_m']} m</b></td></tr>
                <tr><td>🚰 Drainage Cap.</td>
                    <td><b>{row['drainage_capacity_mm_hr']} mm/hr</b></td></tr>
            </table>
            <hr style="margin:4px 0;">
            <div style="text-align:center;padding:4px;border-radius:4px;
                        background:{'#ff4d4d' if risk=='High' else '#ffa500' if risk=='Moderate' else '#2ecc71'};
                        color:white;font-weight:bold;font-size:14px;">
                {risk} Flood Risk
            </div>
        </div>
        """

        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"<b>{row['location']}</b> — {risk} Risk",
            icon=folium.Icon(color=color, icon=icon, prefix="fa"),
        ).add_to(groups[risk])

        # Transparent heatmap-style circle behind the marker
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=18,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.18,
            weight=1.5,
        ).add_to(groups[risk])

    for group in groups.values():
        group.add_to(fmap)

    # ── Layer control ─────────────────────────────────────────────────────────
    folium.LayerControl(collapsed=False).add_to(fmap)

    # ── Legend (HTML macro) ───────────────────────────────────────────────────
    legend_html = """
    <div style="
        position: fixed;
        bottom: 30px; left: 30px;
        z-index: 1000;
        background-color: white;
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: 0 3px 14px rgba(0,0,0,0.25);
        font-family: Arial, sans-serif;
        font-size: 13px;
        line-height: 1.7;
    ">
        <b style="font-size:14px;">🌊 Flood Risk Legend</b><br>
        <span style="color:#d9534f;">&#9679;</span>&nbsp;<b>High</b> — Immediate action needed<br>
        <span style="color:#f0ad4e;">&#9679;</span>&nbsp;<b>Moderate</b> — Monitor closely<br>
        <span style="color:#2ecc71;">&#9679;</span>&nbsp;<b>Low</b> — Safe zone<br>
        <hr style="margin:6px 0 4px;">
        <small style="color:#888;">Click a marker for full details</small>
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))

    # ── Summary title banner ──────────────────────────────────────────────────
    risk_counts = df["flood_risk"].value_counts().to_dict()
    title_html = f"""
    <div style="
        position: fixed;
        top: 10px; left: 50%;
        transform: translateX(-50%);
        z-index: 1000;
        background: rgba(255,255,255,0.92);
        padding: 8px 20px;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        font-family: Arial, sans-serif;
        font-size: 13px;
        text-align: center;
    ">
        <b>🏙 Urban Flood Intelligence Engine</b>&nbsp;&nbsp;|&nbsp;&nbsp;
        <span style="color:#d9534f;">⬤ High: {risk_counts.get('High', 0)}</span>&nbsp;&nbsp;
        <span style="color:#f0ad4e;">⬤ Moderate: {risk_counts.get('Moderate', 0)}</span>&nbsp;&nbsp;
        <span style="color:#2ecc71;">⬤ Low: {risk_counts.get('Low', 0)}</span>
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(title_html))

    return fmap


def main():
    print(f"📂  Loading data from: {CSV_PATH}")
    df = load_data(CSV_PATH)

    print(f"📍  {len(df)} locations loaded.")
    counts = df["flood_risk"].value_counts()
    for level in ("High", "Moderate", "Low"):
        print(f"    {level:8s}: {counts.get(level, 0)}")

    print("\n🗺   Building map …")
    fmap = build_map(df)

    fmap.save(HTML_PATH)
    print(f"✅  Map saved → {HTML_PATH}")

    print("🌐  Opening in browser …")
    webbrowser.open(f"file://{HTML_PATH}")


if __name__ == "__main__":
    main()
