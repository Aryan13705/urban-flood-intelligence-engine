# Urban Flood Intelligence Engine

An AI-driven decision support platform for urban flood prediction and management. This system provides a comprehensive API and an interactive web dashboard to monitor flood risks, calculate city ward readiness scores, and leverage machine learning for predictive analysis based on infrastructure and environmental data.

## Features

- **Interactive Dashboard:** A visual interface providing real-time mappings, insights, and actionable recommendations for various city wards.
- **Rule-Based & ML Predictions:** Evaluate flood risks using both predefined environmental thresholds and trained machine learning models.
- **Pre-Monsoon Readiness:** Calculates readiness scores for wards based on drainage infrastructure, drain cleaning history, and pump availability.
- **Data Visualization:** Generates and displays interactive Folium-based maps (`flood_map.html`) to visualize high-risk zones.
- **RESTful API:** Exposes robust endpoints for data retrieval, risk prediction, and city-level summary aggregates.

## Tech Stack

- **Backend:** Python, Flask
- **Data & ML:** Pandas, NumPy, Scikit-Learn, Joblib
- **Mapping:** Folium (Frontend uses Leaflet integrations)
- **Frontend:** HTML, CSS, JavaScript (via Flask Templates)

## Project Structure

```
urban-flood-intelligence-engine/
├── app.py                  # Main Flask application and API routing
├── ml_model.py             # Machine learning prediction logic
├── flood_risk.py           # Rule-based flood risk calculation
├── readiness_score.py      # Ward pre-monsoon readiness calculator
├── flood_map.py            # Generates Folium maps based on data
├── flood_data.csv          # Ward and infrastructure dataset
├── flood_model.pkl         # Trained ML model weights
├── flood_encoder.pkl       # ML categorical encoder
├── requirements.txt        # Python dependencies
├── static/                 # Static assets (CSS, JS, Images)
└── templates/              # HTML templates (e.g., dashboard.html)
```

## Installation

1. **Clone or navigate to the repository:**
   ```bash
   cd urban-flood-intelligence-engine
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Start the Flask Server:**
   ```bash
   source .venv/bin/activate
   python app.py
   ```
2. **Access the Dashboard:**
   Open your browser and navigate to [http://127.0.0.1:5000/dashboard](http://127.0.0.1:5000/dashboard) to view the interactive web dashboard.
3. **Health Check:**
   Navigate to [http://127.0.0.1:5000/](http://127.0.0.1:5000/) for a service health status.

## API Endpoints Overview

- `GET /api/summary` - Aggregate counts of wards per risk level.
- `GET /api/wards` - Full detail list for all wards (includes risk, readiness, infrastructure stats).
- `GET /api/readiness-summary` - City-level readiness aggregates and top action items.
- `POST /api/predict` - Rule-based prediction from provided JSON inputs.
- `POST /api/ml/predict` - ML-based prediction from JSON body features.
