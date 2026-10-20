"""
=============================================================
AI AQUATIC HABITAT ASSESSMENT
Autonomous Comprehensive Audit & Verification Test Suite
=============================================================

Independent testing across all 7 requirements:
  A. ML Prediction & Feature Validation
  B. Controlled Firebase Fixtures & Failure Modes
  C. Flask Backend & REST API Integrity
  D. HSS Scientific Scoring & Boundary Conditions
  E. What-If Simulator & Calibration Endpoints
  F. Frontend Integrity & Visual State Attributes
  G. Controlled End-to-End Simulation Pipeline
=============================================================
"""

import os
import sys
import math
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Ensure stdout is UTF-8 clean for Windows terminals
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is on sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Global test tracking
test_records = []

def record_test(name, passed, detail=""):
    test_records.append({"name": name, "passed": bool(passed), "detail": str(detail)})
    status_tag = "[PASS]" if passed else "[FAIL]"
    print(f"  {status_tag} {name}" + (f" - {detail}" if detail else ""))

def print_section(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")


# =============================================================
# SUITE A: ML MODULE & PREDICTIONS
# =============================================================

print_section("SUITE A: Machine Learning Model & Prediction Validation")

try:
    import ml.predict_water_quality as ml_mod
    from ml.predict_water_quality import (
        load_models,
        get_model_status,
        predict_water_quality,
        predict_from_raw_conductance,
        validate_sensor_inputs,
        tds_to_sp_conductance,
        set_tds_conversion_factor,
        get_tds_conversion_factor,
        PH_MODEL_PATH,
        DO_MODEL_PATH,
        FEATURE_NAMES,
    )
    record_test("ML prediction module imported successfully", True)
except Exception as e:
    record_test("ML prediction module import", False, str(e))
    print("FATAL: Cannot continue ML tests.")
    sys.exit(1)

# A1. Model files existence & loading
record_test("pH model artifact exists on disk", os.path.exists(PH_MODEL_PATH), PH_MODEL_PATH)
record_test("DO model artifact exists on disk", os.path.exists(DO_MODEL_PATH), DO_MODEL_PATH)

models_ok = load_models()
record_test("Both ML models load into memory", models_ok)

status = get_model_status()
record_test("Model status reports loaded=True", status.get('loaded') is True)
record_test("Model status reports no load error", status.get('error') is None)

# A2. Feature names & order verification
try:
    ph_features = list(ml_mod._ph_model.feature_names_in_)
    do_features = list(ml_mod._do_model.feature_names_in_)
    expected_features = ['water_temperature', 'sp_conductance', 'turbidity']

    record_test("pH model feature names match expected order", ph_features == expected_features, f"{ph_features}")
    record_test("DO model feature names match expected order", do_features == expected_features, f"{do_features}")
except Exception as e:
    record_test("Feature names inspection", False, str(e))

# A3. Input Validation - Missing, Null, Types, Ranges
val_valid = validate_sensor_inputs(25.0, 200.0, 5.0)
record_test("Valid inputs pass validation", val_valid['valid'] is True)

# Missing & Null inputs
val_missing_temp = validate_sensor_inputs(None, 200.0, 5.0)
record_test("Missing temperature rejected", val_missing_temp['valid'] is False)

val_missing_tds = validate_sensor_inputs(25.0, None, 5.0)
record_test("Missing TDS rejected", val_missing_tds['valid'] is False)

val_missing_turb = validate_sensor_inputs(25.0, 200.0, None)
record_test("Missing Turbidity rejected", val_missing_turb['valid'] is False)

val_all_missing = validate_sensor_inputs(None, None, None)
record_test("All None inputs rejected", val_all_missing['valid'] is False and len(val_all_missing['errors']) == 3)

# String and Non-numeric
val_str_num = validate_sensor_inputs("25.0", "200.0", "5.0")
record_test("Numeric string inputs coerced properly", val_str_num['valid'] is True)

val_bad_str = validate_sensor_inputs("twenty-five", 200.0, 5.0)
record_test("Non-numeric string rejected", val_bad_str['valid'] is False)

# Negative values
val_neg_temp = validate_sensor_inputs(-10.0, 200.0, 5.0)
record_test("Negative temperature below physical min (-5°C) rejected", val_neg_temp['valid'] is False)

val_neg_tds = validate_sensor_inputs(25.0, -50.0, 5.0)
record_test("Negative TDS rejected", val_neg_tds['valid'] is False)

val_neg_turb = validate_sensor_inputs(25.0, 200.0, -10.0)
record_test("Negative turbidity rejected", val_neg_turb['valid'] is False)

# Extreme values
val_extreme_temp = validate_sensor_inputs(95.0, 200.0, 5.0)
record_test("Extreme temperature (95°C) rejected", val_extreme_temp['valid'] is False)

val_extreme_tds = validate_sensor_inputs(25.0, 99999.0, 5.0)
record_test("Extreme TDS (99,999 ppm) rejected", val_extreme_tds['valid'] is False)

val_extreme_turb = validate_sensor_inputs(25.0, 200.0, 99999.0)
record_test("Extreme turbidity (99,999 NTU) rejected", val_extreme_turb['valid'] is False)

# NaN and Infinity rejection
val_nan_temp = validate_sensor_inputs(float('nan'), 200.0, 5.0)
record_test("NaN temperature rejected", val_nan_temp['valid'] is False)

val_inf_tds = validate_sensor_inputs(25.0, float('inf'), 5.0)
record_test("Infinity TDS rejected", val_inf_tds['valid'] is False)

val_neginf_turb = validate_sensor_inputs(25.0, 200.0, float('-inf'))
record_test("-Infinity turbidity rejected", val_neginf_turb['valid'] is False)

# Ecological sub-arctic domain warning
val_warm = validate_sensor_inputs(28.0, 200.0, 5.0)
has_domain_warning = any("sub-arctic" in w or "warmer" in w for w in val_warm.get('warnings', []))
record_test("Warm water temperature issues sub-arctic baseline warning", has_domain_warning)

# A4. Configurable Calibration Factor
orig_k = get_tds_conversion_factor()
record_test("Default conversion factor is 0.55", abs(orig_k - 0.55) < 1e-4)

# Set custom factor
set_tds_conversion_factor(0.65)
record_test("Configurable conversion factor updated to 0.65", abs(get_tds_conversion_factor() - 0.65) < 1e-4)

# Invalid factor rejection
try:
    set_tds_conversion_factor(0.05)  # Too low
    factor_rejected_low = False
except ValueError:
    factor_rejected_low = True
record_test("Conversion factor < 0.25 rejected", factor_rejected_low)

try:
    set_tds_conversion_factor(2.5)  # Too high
    factor_rejected_high = False
except ValueError:
    factor_rejected_high = True
record_test("Conversion factor > 1.25 rejected", factor_rejected_high)

# Reset factor back to 0.55
set_tds_conversion_factor(0.55)

# A5. Model Predictions & Output Sanity
pred = predict_water_quality(22.0, 150.0, 8.0)
record_test("Valid prediction succeeds", pred['success'] is True)
record_test("Prediction carries is_approximate=True", pred.get('is_approximate') is True)
record_test("Prediction has conversion_warning", "approximate" in pred.get('conversion_warning', ''))
record_test("Predicted pH is finite and within physical range (0-14)", 0 <= pred['ph'] <= 14, f"pH={pred['ph']}")
record_test("Predicted DO is finite and non-negative", pred['do'] >= 0, f"DO={pred['do']}")

# Per-prediction conversion factor override
pred_custom_k = predict_water_quality(22.0, 150.0, 8.0, conversion_factor=0.70)
record_test("Prediction accepts per-call conversion_factor override", pred_custom_k['conversion_factor'] == 0.70)

# Raw conductance prediction
pred_raw = predict_from_raw_conductance(15.0, 0.082, 4.0)
record_test("Raw conductance prediction succeeds", pred_raw['success'] is True)
record_test("Raw conductance pH is plausible", 6.0 <= pred_raw['ph'] <= 9.0, f"pH={pred_raw['ph']}")
record_test("Raw conductance DO is plausible", 8.0 <= pred_raw['do'] <= 16.0, f"DO={pred_raw['do']}")

# Raw conductance NaN rejection
pred_raw_nan = predict_from_raw_conductance(float('nan'), 0.082, 4.0)
record_test("Raw conductance prediction rejects NaN", pred_raw_nan['success'] is False)


# =============================================================
# SUITE B: CONTROLLED FIREBASE FIXTURES & FAILURE MODES
# =============================================================

print_section("SUITE B: Controlled Firebase Fixtures & Failure Modes")

from backend.app import app

client = app.test_client()

# B1. Successful reading retrieval via mock fixture
mock_valid_payload = {
    "temperature": 24.5,
    "tds": 180.0,
    "turbidity": 6.2,
    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
    "uptimeMs": 450000,
    "wifiRSSI": -55,
    "device_id": "ESP32_AQUATIC_01"
}

with patch('requests.get') as mock_get:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_valid_payload
    mock_get.return_value = mock_resp

    resp = client.get('/api/latest')
    record_test("Firebase successful reading returns HTTP 200", resp.status_code == 200)
    data = json.loads(resp.data)
    record_test("Response contains success=True", data.get('success') is True)
    record_test("Response contains ML predictions", data.get('predictions', {}).get('ph') is not None)
    record_test("Response contains assessment score", data.get('assessment', {}).get('hss') is not None)
    record_test("Response is marked not stale", data.get('is_stale') is False)

# B2. Missing Database Values in Firebase
mock_missing_payload = {
    "temperature": 24.5,
    "uptimeMs": 450000
    # tds and turbidity missing
}

with patch('requests.get') as mock_get:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_missing_payload
    mock_get.return_value = mock_resp

    resp = client.get('/api/latest')
    record_test("Missing sensor values in Firebase handled (HTTP 200)", resp.status_code == 200)
    data = json.loads(resp.data)
    record_test("Prediction status reports missing_inputs", data.get('prediction_status') == 'missing_inputs')
    record_test("Assessment category is Unavailable on missing data", data.get('assessment', {}).get('category') == 'Unavailable')
    record_test("Assessment score is None on missing data", data.get('assessment', {}).get('hss') is None)

# B3. Malformed Records (strings in numeric fields)
mock_malformed_payload = {
    "temperature": "CORRUPTED",
    "tds": "NULL",
    "turbidity": [1, 2, 3]
}

with patch('requests.get') as mock_get:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_malformed_payload
    mock_get.return_value = mock_resp

    resp = client.get('/api/latest')
    record_test("Malformed records return HTTP 200 with invalid_inputs", resp.status_code == 200)
    data = json.loads(resp.data)
    record_test("Prediction status reports invalid_inputs", data.get('prediction_status') == 'invalid_inputs')

# B4. Invalid Timestamps (non-numeric, corrupted string)
mock_bad_time_payload = dict(mock_valid_payload)
mock_bad_time_payload['timestamp'] = "NOT_A_TIMESTAMP"

with patch('requests.get') as mock_get:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_bad_time_payload
    mock_get.return_value = mock_resp

    resp = client.get('/api/latest')
    record_test("Corrupted timestamp does not crash backend", resp.status_code == 200)

# B5. Stale Readings (Age > 120 seconds)
old_timestamp_ms = int((datetime.now(timezone.utc).timestamp() - 300) * 1000)  # 300s old
mock_stale_payload = dict(mock_valid_payload)
mock_stale_payload['timestamp'] = old_timestamp_ms

with patch('requests.get') as mock_get:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_stale_payload
    mock_get.return_value = mock_resp

    resp = client.get('/api/latest')
    data = json.loads(resp.data)
    record_test("Stale reading (> 120s) triggers is_stale=True", data.get('is_stale') is True)
    record_test("Stale reason is provided", "stale" in data.get('stale_reason', '').lower())

# B6. Firebase Connection Failure (Network error)
import requests
with patch('requests.get', side_effect=requests.exceptions.ConnectionError("Connection refused")):
    resp = client.get('/api/latest')
    record_test("Firebase network error returns HTTP 502", resp.status_code == 502)
    data = json.loads(resp.data)
    record_test("Error response reports success=False", data.get('success') is False)

# B7. Empty Firebase Database (None returned)
with patch('requests.get') as mock_get:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = None
    mock_get.return_value = mock_resp

    resp = client.get('/api/latest')
    record_test("Empty database returns HTTP 404", resp.status_code == 404)


# =============================================================
# SUITE C: FLASK BACKEND & REST API INTEGRITY
# =============================================================

print_section("SUITE C: REST API Endpoints & Response Integrity")

# C1. Static index page
resp = client.get('/')
record_test("GET / returns HTTP 200", resp.status_code == 200)

# C2. Model status endpoint
resp = client.get('/api/model-status')
record_test("GET /api/model-status returns HTTP 200", resp.status_code == 200)
data = json.loads(resp.data)
record_test("Model status contains 'models'", 'models' in data)
record_test("Model status contains 'conversion_factor'", 'conversion_factor' in data)

# C3. Conversion factor configuration endpoint
resp = client.get('/api/config/conversion-factor')
record_test("GET /api/config/conversion-factor returns HTTP 200", resp.status_code == 200)
data = json.loads(resp.data)
record_test("Conversion config contains guidelines", 'guidelines' in data)

# POST valid conversion factor
resp = client.post('/api/config/conversion-factor',
    data=json.dumps({"factor": 0.60}),
    content_type='application/json'
)
record_test("POST /api/config/conversion-factor updates factor (HTTP 200)", resp.status_code == 200)
set_tds_conversion_factor(0.55)  # reset

# POST invalid conversion factor
resp = client.post('/api/config/conversion-factor',
    data=json.dumps({"factor": 5.0}),
    content_type='application/json'
)
record_test("POST /api/config/conversion-factor rejects out-of-bound factor (HTTP 400)", resp.status_code == 400)

# C4. History proxy endpoint
with patch('requests.get') as mock_get:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"rec1": {"temp": 24}}
    mock_get.return_value = mock_resp

    resp = client.get('/api/history')
    record_test("GET /api/history proxies data (HTTP 200)", resp.status_code == 200)


# =============================================================
# SUITE D: HSS SCIENTIFIC SCORING & BOUNDARY AUDIT
# =============================================================

print_section("SUITE D: Habitat Suitability Score (HSS) & Boundary Audit")

from backend.app import compute_habitat_assessment

# D1. Category & Boundary Matrix
# Requirements:
#   80-100: Excellent
#   60-79 : Good
#   40-59 : Moderate
#   0-39  : Poor

# Perfect conditions (0 deductions -> 100)
h_100 = compute_habitat_assessment(25.0, 200.0, 5.0, predicted_ph=7.5, predicted_do=8.0)
record_test("Score 100 -> Excellent", h_100['hss'] == 100 and h_100['category'] == "Excellent")
record_test("Score 100 has complete assessment flag", h_100.get('is_complete') is True)
record_test("Score 100 provides optimal recommendations", len(h_100['recommendations']) > 0 and "optimal" in h_100['recommendations'][0].lower())

# Moderate turbidity penalty (-12 -> 88) -> Excellent
h_88 = compute_habitat_assessment(25.0, 200.0, 15.0, predicted_ph=7.5, predicted_do=8.0)
record_test("Score 88 -> Excellent", h_88['hss'] == 88 and h_88['category'] == "Excellent")

# Temp penalty (-15) + Severe turbidity (-25) -> 60 -> Good
h_60 = compute_habitat_assessment(35.0, 200.0, 30.0, predicted_ph=7.5, predicted_do=8.0)
record_test("Boundary Score 60 -> Good", h_60['hss'] == 60 and h_60['category'] == "Good", f"HSS={h_60['hss']}")

# Temp penalty (-15) + Severe TDS (-25) + low DO (-15) -> 45 -> Moderate
h_45 = compute_habitat_assessment(35.0, 600.0, 5.0, predicted_ph=7.5, predicted_do=4.5)
record_test("Score 45 -> Moderate", h_45['hss'] == 45 and h_45['category'] == "Moderate")

# Boundary Score 40:
# Temp (-15) + Severe TDS (-25) + Severe Turbidity (-25) + DO critical (-30) -> 5 -> Poor
h_poor = compute_habitat_assessment(38.0, 700.0, 50.0, predicted_ph=5.0, predicted_do=3.0)
record_test("Severe penalties clamp to Poor category", h_poor['category'] == "Poor" and h_poor['hss'] <= 39)

# Zero clamp: all deductions total 15+25+25+20+30 = 115 -> clamped to 0
record_test("Score clamped to minimum 0", h_poor['hss'] >= 0)

# D2. Missing Parameter Handling
h_all_none = compute_habitat_assessment(None, None, None)
record_test("All None inputs -> Category Unavailable", h_all_none['category'] == "Unavailable")
record_test("All None inputs -> Score is None (not 100)", h_all_none['hss'] is None)

# Partial inputs without ML predictions
h_partial = compute_habitat_assessment(25.0, 200.0, 5.0, predicted_ph=None, predicted_do=None)
record_test("Assessment without ML is flagged is_complete=False", h_partial.get('is_complete') is False)
record_test("Assessment parameter status tracks unassessed ML targets", h_partial['parameter_status']['ph'] == 'unassessed')

# D3. Recommendation Consistency
# Check that conflicting low and high recommendations don't appear together
record_test("No conflicting pH recommendations simultaneously",
    not (any("acidification" in r for r in h_100['recommendations']) and any("alkalinity" in r for r in h_100['recommendations']))
)


# =============================================================
# SUITE E: INTERVENTION SIMULATOR & SAFETY
# =============================================================

print_section("SUITE E: Intervention Simulator & Safety Verification")

# E1. Valid simulation request
sim_payload = {
    "temperature": 26.0,
    "tds": 220.0,
    "turbidity": 8.0
}
resp = client.post('/api/simulate', data=json.dumps(sim_payload), content_type='application/json')
record_test("POST /api/simulate returns HTTP 200", resp.status_code == 200)
sim_res = json.loads(resp.data)
record_test("Simulation marked with simulated=True", sim_res.get('simulated') is True)
record_test("Simulation returns predictions", sim_res.get('predictions') is not None)
record_test("Simulation returns assessment", sim_res.get('assessment', {}).get('hss') is not None)

# E2. Simulation with custom conversion factor
sim_k_payload = dict(sim_payload)
sim_k_payload['conversion_factor'] = 0.65
resp = client.post('/api/simulate', data=json.dumps(sim_k_payload), content_type='application/json')
record_test("Simulation accepts custom conversion_factor", resp.status_code == 200)
data = json.loads(resp.data)
record_test("Conversion info reports custom factor", data.get('conversion_info', {}).get('conversion_factor') == 0.65)

# E3. Simulation invalid inputs
# Missing parameter
resp = client.post('/api/simulate', data=json.dumps({"temperature": 25.0}), content_type='application/json')
record_test("Simulation rejects missing parameters (HTTP 400)", resp.status_code == 400)

# NaN parameter
resp = client.post('/api/simulate', data=json.dumps({"temperature": "NaN", "tds": 200, "turbidity": 5}), content_type='application/json')
record_test("Simulation rejects NaN values (HTTP 400)", resp.status_code == 400)

# Empty body
resp = client.post('/api/simulate', data="", content_type='application/json')
record_test("Simulation rejects empty body (HTTP 400)", resp.status_code == 400)

# E4. Data safety: Verify simulation does NOT write to Firebase
with patch('requests.put') as mock_put, patch('requests.post') as mock_post, patch('requests.patch') as mock_patch:
    client.post('/api/simulate', data=json.dumps(sim_payload), content_type='application/json')
    record_test("Simulation never calls Firebase PUT", not mock_put.called)
    record_test("Simulation never calls Firebase POST", not mock_post.called)
    record_test("Simulation never calls Firebase PATCH", not mock_patch.called)


# =============================================================
# SUITE F: FRONTEND INTEGRITY & COMPONENT AUDIT
# =============================================================

print_section("SUITE F: Frontend Integrity & UI Components Audit")

frontend_dir = os.path.join(project_root, 'frontend')

with open(os.path.join(frontend_dir, 'index.html'), 'r', encoding='utf-8') as f:
    html_content = f.read()

with open(os.path.join(frontend_dir, 'script.js'), 'r', encoding='utf-8') as f:
    js_content = f.read()

with open(os.path.join(frontend_dir, 'style.css'), 'r', encoding='utf-8') as f:
    css_content = f.read()

# F1. UI Elements existence in HTML
record_test("HTML contains simulator section", 'simulator-section' in html_content)
record_test("HTML contains simTemperature slider", 'id="simTemperature"' in html_content)
record_test("HTML contains simTds slider", 'id="simTds"' in html_content)
record_test("HTML contains simTurbidity slider", 'id="simTurbidity"' in html_content)
record_test("HTML contains simRunButton", 'id="simRunButton"' in html_content)
record_test("HTML contains simResetButton", 'id="simResetButton"' in html_content)
record_test("HTML contains Live vs Simulated comparative cards",
    'sim-card-live' in html_content and 'sim-card-simulated' in html_content)

# F2. JavaScript integrity
record_test("JS polls /api/latest", '/api/latest' in js_content)
record_test("JS queries /api/history", '/api/history' in js_content)
record_test("JS executes POST to /api/simulate", '/api/simulate' in js_content)
record_test("JS handles simResetButton", 'simResetButton' in js_content)
record_test("JS updates Live values in simulator", 'updateSimulatorLiveValues' in js_content)
record_test("JS preserves analyzeWaterQuality fallback", 'analyzeWaterQuality' in js_content)

# F3. CSS visual styling
record_test("CSS styles simulator controls", '.simulator-controls' in css_content)
record_test("CSS provides dashed border for simulated card", 'sim-card-simulated' in css_content)
record_test("CSS provides stale visual state styling", '.stale' in css_content)


# =============================================================
# SUITE G: CONTROLLED END-TO-END PIPELINE SIMULATION
# =============================================================

print_section("SUITE G: Controlled End-to-End Pipeline Simulation")

# End-to-end flow:
# Simulated IoT sensor packet -> Firebase RTDB fixture -> Flask backend (/api/latest)
# -> ML prediction (pH + DO) -> HSS engine -> Recommendations -> API output.

iot_sensor_packet = {
    "temperature": 23.8,
    "tds": 210.0,
    "tdsVoltage": 1.42,
    "tdsADC": 1765,
    "turbidity": 7.5,
    "turbidityVoltage": 2.15,
    "turbidityADC": 2670,
    "ph": None,             # Hardware sensor not installed
    "dissolvedOxygen": None, # Hardware sensor not installed
    "uptimeMs": 789120,
    "wifiRSSI": -62,
    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
    "device_id": "ESP32_STATION_KLGO"
}

with patch('requests.get') as mock_fb:
    mock_fb_resp = MagicMock()
    mock_fb_resp.status_code = 200
    mock_fb_resp.json.return_value = iot_sensor_packet
    mock_fb.return_value = mock_fb_resp

    e2e_resp = client.get('/api/latest')
    record_test("End-to-End request completes with HTTP 200", e2e_resp.status_code == 200)

    e2e_data = json.loads(e2e_resp.data)

    # 1. Pipeline ingested physical sensor data
    record_test("E2E: Physical sensor readings captured accurately",
        e2e_data['sensor_data']['temperature'] == 23.8 and
        e2e_data['sensor_data']['tds'] == 210.0 and
        e2e_data['sensor_data']['turbidity'] == 7.5
    )

    # 2. ML predictions generated
    ph_out = e2e_data['predictions']['ph']
    do_out = e2e_data['predictions']['do']
    record_test("E2E: ML predicted pH generated", ph_out is not None and 5.0 <= ph_out <= 9.0, f"pH={ph_out}")
    record_test("E2E: ML predicted DO generated", do_out is not None and 8.0 <= do_out <= 15.0, f"DO={do_out}")

    # 3. TDS to Conductance conversion recorded
    sp_cond_est = e2e_data['conversion_info']['sp_conductance_estimated_ms_cm']
    record_test("E2E: Estimated conductance computed and disclosed", sp_cond_est is not None and sp_cond_est > 0, f"sp_cond={sp_cond_est} mS/cm")

    # 4. HSS assessment calculated
    hss_score = e2e_data['assessment']['hss']
    hss_cat = e2e_data['assessment']['category']
    record_test("E2E: Habitat Suitability Score calculated", hss_score is not None and 0 <= hss_score <= 100, f"HSS={hss_score}")
    record_test("E2E: Assessment category assigned", hss_cat in ("Excellent", "Good", "Moderate", "Poor"), f"Category={hss_cat}")

    # 5. Ecological recommendations generated
    recs = e2e_data['assessment']['recommendations']
    record_test("E2E: Actionable recommendations returned", isinstance(recs, list) and len(recs) > 0)


# =============================================================
# FINAL AUDIT SUMMARY
# =============================================================

print_section("AUDIT TEST SUITE RESULTS SUMMARY")

total_tests = len(test_records)
passed_tests = sum(1 for t in test_records if t['passed'])
failed_tests = total_tests - passed_tests

print(f"\n  Total Tests Executed : {total_tests}")
print(f"  Tests Passed         : {passed_tests}")
print(f"  Tests Failed         : {failed_tests}")

if failed_tests > 0:
    print("\n  FAILED TESTS BREAKDOWN:")
    for t in test_records:
        if not t['passed']:
            print(f"    [FAIL] {t['name']}" + (f" - {t['detail']}" if t['detail'] else ""))

print(f"\n{'='*65}")
if failed_tests == 0:
    print(f"  ALL {total_tests} AUDIT TESTS PASSED SUCCESSFULLY!")
else:
    print(f"  {failed_tests} TEST(S) FAILED - ATTENTION REQUIRED!")
print(f"{'='*65}\n")

if failed_tests > 0:
    sys.exit(1)
