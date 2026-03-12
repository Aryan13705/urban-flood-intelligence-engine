/**
 * dashboard.js — Urban Flood Intelligence Engine
 * Fetches API data, renders Leaflet map, populates Chart.js charts,
 * and handles ward list interactions.
 */

// ── Constants ─────────────────────────────────────────────────────────────────
const RISK_COLOR = { High: '#ff4d4d', Moderate: '#f0a500', Low: '#2ecc71' };
const GRADE_COLOR = { A: '#2ecc71', B: '#58a6ff', C: '#f0a500', D: '#ff7043', F: '#ff4d4d' };
const MAP_TILE = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

// ── State ─────────────────────────────────────────────────────────────────────
let allWards = [];
let summary = {};
let map = null;
let markers = {};
let activeWardId = null;
let riskFilter = 'all';
let doughnutChart, barChart;

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await loadData();
        initMap();
        renderWardList(allWards);
        renderTopStats();
        renderDoughnut();
        renderBarChart();
        renderAlerts();
        hideLoading();
    } catch (err) {
        console.error('Dashboard boot error:', err);
        document.querySelector('.loading-text').textContent = 'Error loading data — check console.';
    }
});

// ── Data fetch ────────────────────────────────────────────────────────────────
async function loadData() {
    const [wardsRes, sumRes] = await Promise.all([
        fetch('/api/wards'),
        fetch('/api/readiness-summary'),
    ]);
    const wardsJson = await wardsRes.json();
    const sumJson = await sumRes.json();
    allWards = wardsJson.wards;
    summary = sumJson;
}

// ── Map ───────────────────────────────────────────────────────────────────────
function initMap() {
    const centre = [
        allWards.reduce((s, w) => s + w.coordinates.lat, 0) / allWards.length,
        allWards.reduce((s, w) => s + w.coordinates.lon, 0) / allWards.length,
    ];

    map = L.map('map', { zoomControl: false, attributionControl: false }).setView(centre, 12);

    L.tileLayer(MAP_TILE, {
        maxZoom: 18,
        subdomains: 'abcd',
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    allWards.forEach(ward => placeMarker(ward));
}

function placeMarker(ward) {
    const color = RISK_COLOR[ward.flood_risk];
    const lat = ward.coordinates.lat;
    const lon = ward.coordinates.lon;

    // Glow circle
    const circle = L.circleMarker([lat, lon], {
        radius: 18,
        color: color,
        fillColor: color,
        fillOpacity: 0.12,
        weight: 1,
    }).addTo(map);

    // Main circle marker
    const marker = L.circleMarker([lat, lon], {
        radius: 9,
        color: color,
        fillColor: color,
        fillOpacity: 0.9,
        weight: 2,
    }).addTo(map);

    marker.bindTooltip(
        `<b>${ward.location}</b><br>${ward.flood_risk} Risk &nbsp;|&nbsp; Score: ${ward.readiness_score}`,
        { direction: 'top', className: 'map-tooltip' }
    );

    marker.on('click', () => selectWard(ward.ward_id));

    markers[ward.ward_id] = { marker, circle };
}

function highlightMarker(wardId) {
    Object.entries(markers).forEach(([id, { marker, circle }]) => {
        const ward = allWards.find(w => w.ward_id === id);
        const color = RISK_COLOR[ward.flood_risk];
        const isActive = id === wardId;
        marker.setStyle({ radius: isActive ? 14 : 9, weight: isActive ? 3 : 2, fillOpacity: isActive ? 1 : 0.9 });
        circle.setStyle({ fillOpacity: isActive ? 0.3 : 0.12 });
    });
    const ward = allWards.find(w => w.ward_id === wardId);
    if (ward) map.panTo([ward.coordinates.lat, ward.coordinates.lon], { animate: true, duration: 0.5 });
}

// Map layer toggles
document.querySelectorAll('.map-toggle-btn[data-layer]').forEach(btn => {
    btn.addEventListener('click', () => {
        btn.classList.toggle('active');
    });
});

// ── Ward List ──────────────────────────────────────────────────────────────────
function renderWardList(wards) {
    const container = document.getElementById('wardList');
    container.innerHTML = '';
    const sorted = [...wards].sort((a, b) => a.readiness_score - b.readiness_score);
    sorted.forEach(ward => {
        const card = document.createElement('div');
        card.className = `ward-card${activeWardId === ward.ward_id ? ' active' : ''}`;
        card.dataset.wardId = ward.ward_id;
        card.innerHTML = `
      <div class="ward-risk-dot ${ward.flood_risk}"></div>
      <div class="ward-info">
        <div class="ward-name">${ward.location}</div>
        <div class="ward-meta">${ward.flood_risk} Risk &nbsp;·&nbsp; Score ${ward.readiness_score}</div>
      </div>
      <div class="grade-badge ${ward.readiness_grade}">${ward.readiness_grade}</div>
    `;
        card.addEventListener('click', () => selectWard(ward.ward_id));
        container.appendChild(card);
    });
}

// Filter buttons
document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        riskFilter = btn.dataset.filter;
        const filtered = riskFilter === 'all'
            ? allWards
            : allWards.filter(w => w.flood_risk === riskFilter);
        renderWardList(filtered);
    });
});

// ── Ward Selection ─────────────────────────────────────────────────────────────
function selectWard(wardId) {
    activeWardId = wardId;

    // Update card active state
    document.querySelectorAll('.ward-card').forEach(c => {
        c.classList.toggle('active', c.dataset.wardId === wardId);
    });

    highlightMarker(wardId);

    const ward = allWards.find(w => w.ward_id === wardId);
    if (ward) renderDetail(ward);
}

// ── Top Stats ─────────────────────────────────────────────────────────────────
function renderTopStats() {
    const rb = summary.risk_breakdown || {};
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('statTotal', summary.total_wards);
    set('statHigh', rb.High ?? 0);
    set('statMod', rb.Moderate ?? 0);
    set('statLow', rb.Low ?? 0);
    set('statAvgScore', summary.avg_readiness);
}

// ── Doughnut Chart ─────────────────────────────────────────────────────────────
function renderDoughnut() {
    const rb = summary.risk_breakdown || {};
    const ctx = document.getElementById('doughnutChart').getContext('2d');
    doughnutChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['High', 'Moderate', 'Low'],
            datasets: [{
                data: [rb.High ?? 0, rb.Moderate ?? 0, rb.Low ?? 0],
                backgroundColor: ['rgba(255,77,77,0.85)', 'rgba(240,165,0,0.85)', 'rgba(46,204,113,0.85)'],
                borderWidth: 0,
                hoverOffset: 6,
            }],
        },
        options: {
            cutout: '72%',
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed} wards` } },
            },
            animation: { duration: 800 },
        },
    });
}

// ── Readiness Bar Chart ────────────────────────────────────────────────────────
function renderBarChart() {
    const sorted = [...allWards].sort((a, b) => a.readiness_score - b.readiness_score).slice(0, 12);
    const ctx = document.getElementById('barChart').getContext('2d');
    barChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(w => w.location.split(' ')[0]),
            datasets: [{
                label: 'Readiness',
                data: sorted.map(w => w.readiness_score),
                backgroundColor: sorted.map(w => {
                    const g = w.readiness_grade;
                    return GRADE_COLOR[g] + 'cc';
                }),
                borderRadius: 4,
                borderSkipped: false,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#7d8590', font: { size: 9 } } },
                y: { grid: { display: false }, ticks: { color: '#7d8590', font: { size: 9 } } },
            },
            plugins: {
                legend: { display: false }, tooltip: {
                    callbacks: { label: ctx => ` Score: ${ctx.parsed.x.toFixed(1)}` }
                }
            },
            animation: { duration: 600 },
        },
    });
}

// ── Ward Detail ────────────────────────────────────────────────────────────────
function renderDetail(ward) {
    const panel = document.getElementById('wardDetail');
    const scoreColor = ward.readiness_score >= 65 ? 'var(--risk-low)'
        : ward.readiness_score >= 35 ? 'var(--risk-mod)'
            : 'var(--risk-high)';

    const subBars = Object.entries(ward.sub_scores || {}).map(([key, val]) => {
        const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        const barColor = val >= 65 ? 'var(--risk-low)' : val >= 35 ? 'var(--risk-mod)' : 'var(--risk-high)';
        return `
      <div class="sub-bar-item">
        <div class="sub-bar-label"><span>${label}</span><span>${val}</span></div>
        <div class="sub-bar-track">
          <div class="sub-bar-fill" style="width:${val}%;background:${barColor};"></div>
        </div>
      </div>`;
    }).join('');

    const recs = (ward.recommendations || []).map(r => `<div class="rec-item">${r}</div>`).join('');

    panel.innerHTML = `
    <div class="detail-header">
      <div>
        <div class="detail-title">${ward.location}</div>
        <div class="detail-id">${ward.ward_id} &nbsp;·&nbsp; Pop. ${ward.population.toLocaleString()}</div>
      </div>
      <div class="risk-badge ${ward.flood_risk}">${ward.flood_risk}</div>
    </div>

    <div class="score-ring-wrap">
      <div class="score-val" style="color:${scoreColor}">${ward.readiness_score}</div>
      <div class="score-sub">Readiness Score &nbsp;|&nbsp; Grade <b>${ward.readiness_grade}</b></div>
    </div>

    <div class="detail-grid">
      <div class="detail-cell"><div class="dc-label">Rainfall</div><div class="dc-val">${ward.inputs.rainfall_mm_hr} mm/hr</div></div>
      <div class="detail-cell"><div class="dc-label">Elevation</div><div class="dc-val">${ward.inputs.elevation_m} m</div></div>
      <div class="detail-cell"><div class="dc-label">Drainage Cap.</div><div class="dc-val">${ward.inputs.drainage_capacity_mm_hr} mm/hr</div></div>
      <div class="detail-cell"><div class="dc-label">Area</div><div class="dc-val">${ward.area_km2} km²</div></div>
      <div class="detail-cell"><div class="dc-label">Drain Length</div><div class="dc-val">${ward.infrastructure.drain_length_km} km</div></div>
      <div class="detail-cell"><div class="dc-label">Pumps</div><div class="dc-val">${ward.infrastructure.pump_count}</div></div>
      <div class="detail-cell"><div class="dc-label">Last Cleaned</div><div class="dc-val">${ward.infrastructure.days_since_last_drain_clean}d ago</div></div>
      <div class="detail-cell"><div class="dc-label">Flood Events</div><div class="dc-val">${ward.infrastructure.historical_flood_events} (5yr)</div></div>
    </div>

    <div class="section-label" style="margin-top:10px;">Readiness Breakdown</div>
    <div class="sub-bars">${subBars}</div>

    <div class="section-label" style="margin-top:6px;">Recommendations</div>
    <div class="recs-list">${recs}</div>
  `;
}

// ── Alerts Panel ───────────────────────────────────────────────────────────────
function renderAlerts() {
    const container = document.getElementById('alertList');
    const critical = [...allWards]
        .filter(w => ['D', 'F'].includes(w.readiness_grade))
        .sort((a, b) => a.readiness_score - b.readiness_score)
        .slice(0, 5);

    container.innerHTML = critical.length
        ? critical.map(w => `
        <div class="alert-item">
          <span class="alert-ward">${w.ward_id}</span>
          <span class="alert-msg">${w.location} — Score ${w.readiness_score} (Grade ${w.readiness_grade})</span>
        </div>`).join('')
        : '<div style="color:var(--text-muted);font-size:11px;padding:4px 0;">No critical wards 🎉</div>';
}

// ── Loading overlay ────────────────────────────────────────────────────────────
function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    overlay.classList.add('hidden');
    setTimeout(() => overlay.remove(), 600);
}
