"""
=============================================================
AI AQUATIC HABITAT ASSESSMENT
Flask Backend
=============================================================

Serves the dashboard and provides API endpoints for:
  - Latest sensor data with ML predictions
  - Historical sensor data
  - Intervention simulator
  - Water quality assessment (HSS)

=============================================================
"""

from flask import Flask, jsonify, request, send_from_directory
import os
import sys
import requests
import logging
from datetime import datetime, timezone

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# PROJECT PATH SETUP
# ============================================================

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

import math
from ml.predict_water_quality import (
    predict_water_quality,
    predict_from_raw_conductance,
    load_models,
    get_model_status,
    tds_to_sp_conductance,
    get_tds_conversion_factor,
    set_tds_conversion_factor,
    TDS_CONDUCTANCE_FACTOR,
)

# In-memory tracking for ESP32 uptime freeze detection across poll cycles
_device_tracker = {
    'last_uptime_ms': None,
    'last_change_time': None,
}


# ============================================================
# FLASK APP & CORS CONFIGURATION
# ============================================================

app = Flask(__name__, static_folder=os.path.join(project_root, 'frontend'))

ALLOWED_ORIGINS = {
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:5000",
    "http://localhost:5000",
}

# Attempt to initialize Flask-CORS if available, otherwise use native Flask hooks
try:
    from flask_cors import CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": list(ALLOWED_ORIGINS),
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    })
    logger.info("Flask-CORS extension initialized.")
except ImportError:
    logger.info("flask-cors not available; using native Flask CORS handlers.")


@app.before_request
def handle_api_options_preflight():
    """Handle preflight OPTIONS requests for /api/* routes from allowed frontend origins."""
    if request.method == "OPTIONS" and request.path.startswith("/api/"):
        origin = request.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            response = app.make_default_options_response()
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Max-Age"] = "86400"
            return response


@app.after_request
def apply_cors_headers(response):
    """Add restricted CORS headers to /api/* responses for permitted origins."""
    if request.path.startswith("/api/"):
        origin = request.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Vary"] = "Origin"
    return response


# ============================================================
# FIREBASE CONFIGURATION
# ============================================================

FIREBASE_LATEST_URL = (
    "https://aquatic-habitat-system-default-rtdb"
    ".asia-southeast1.firebasedatabase.app"
    "/sensorData/latest.json"
)
FIREBASE_HISTORY_URL = (
    "https://aquatic-habitat-system-default-rtdb"
    ".asia-southeast1.firebasedatabase.app"
    "/sensorData/history.json"
)

# How many seconds before sensor data is considered stale
STALE_THRESHOLD_SECONDS = 120


# ============================================================
# HSS — HABITAT SUITABILITY SCORE
#
# Rule-based assessment. The thresholds below are drawn from
# the existing frontend implementation and general freshwater
# ecology guidelines.
#
# IMPORTANT: These thresholds have NOT been validated against
# peer-reviewed species-specific tolerance data for any
# particular ecosystem. They provide a general indication
# of water quality for common freshwater habitats.
# ============================================================

# Acceptable ranges for freshwater aquatic habitats
# Each entry: (min, max, penalty_severe, penalty_moderate,
#              moderate_threshold_type)
#
# The scoring is additive-deduction from 100.

WATER_QUALITY_RANGES = {
    'temperature': {
        'ideal_min': 20.0,
        'ideal_max': 32.0,
        'unit': '°C',
        'penalty': 15,
        'problem_template': "Temperature is {status} ({value:.1f}°C, preferred range: 20–32°C).",
        'recommendation': "Monitor water temperature and investigate sources of thermal change.",
    },
    'turbidity': {
        'severe_max': 25.0,
        'moderate_max': 10.0,
        'unit': 'NTU*',
        'penalty_severe': 25,
        'penalty_moderate': 12,
        'problem_template_severe': "High turbidity detected ({value:.1f} NTU*).",
        'problem_template_moderate': "Moderate turbidity detected ({value:.1f} NTU*).",
        'recommendation_severe': "Reduce sediment and soil runoff entering the water body.",
        'recommendation_moderate': "Monitor sediment and runoff entering the water body.",
    },
    'tds': {
        'severe_max': 500.0,
        'moderate_max': 300.0,
        'unit': 'ppm*',
        'penalty_severe': 25,
        'penalty_moderate': 8,
        'problem_template_severe': "High TDS detected ({value:.1f} ppm*).",
        'problem_template_moderate': "Elevated TDS detected ({value:.1f} ppm*).",
        'recommendation_severe': "Investigate possible sources of dissolved salts and contaminants.",
        'recommendation_moderate': "Monitor dissolved solids and investigate possible pollution sources.",
    },
    'ph': {
        'ideal_min': 6.5,
        'ideal_max': 8.5,
        'unit': '',
        'penalty': 20,
        'problem_template': "Predicted pH is {status} ({value:.2f}, preferred range: 6.5–8.5).",
        'recommendation_low': "Investigate potential sources of acidification (acid rain, mine drainage, organic decay).",
        'recommendation_high': "Investigate potential sources of alkalinity (detergent runoff, limestone dissolution).",
    },
    'do': {
        'critical_min': 4.0,
        'low_min': 5.0,
        'unit': 'mg/L',
        'penalty_critical': 30,
        'penalty_low': 15,
        'problem_template_critical': "Predicted Dissolved Oxygen is critically low ({value:.2f} mg/L, minimum: 4.0 mg/L).",
        'problem_template_low': "Predicted Dissolved Oxygen is below optimal ({value:.2f} mg/L, preferred: ≥5.0 mg/L).",
        'recommendation_critical': "Investigate sources of oxygen depletion. Consider aeration if feasible.",
        'recommendation_low': "Monitor dissolved oxygen levels. Reduce organic loading if possible.",
    },
}


def compute_habitat_assessment(temperature, tds, turbidity,
                                predicted_ph=None, predicted_do=None):
    """
    Compute the Habitat Suitability Score (HSS) and generate
    problem descriptions and recommendations.

    Uses a rule-based deduction system starting from 100.
    Categories:
      80–100: Excellent
      60–79 : Good
      40–59 : Moderate
      0–39  : Poor

    Args:
        temperature: Measured water temperature in °C (float or None)
        tds: Measured TDS in ppm (float or None)
        turbidity: Measured turbidity in NTU (float or None)
        predicted_ph: ML-predicted pH (float or None)
        predicted_do: ML-predicted DO in mg/L (float or None)

    Returns:
        dict with hss, category, is_complete, problems, recommendations,
        and parameter_status.
    """
    # Guard: if all inputs are missing or non-finite, assessment is Unavailable
    physical_inputs = [temperature, tds, turbidity]
    valid_physical = [
        p for p in physical_inputs
        if p is not None and not (isinstance(p, (float, int)) and (math.isnan(p) or math.isinf(p)))
    ]

    if len(valid_physical) == 0:
        return {
            'hss': None,
            'category': "Unavailable",
            'is_complete': False,
            'problems': ["Insufficient sensor data: all physical parameters are missing or invalid."],
            'recommendations': ["Ensure ESP32 sensor node is connected and providing real-time measurements."],
            'parameter_status': {
                'temperature': 'missing',
                'tds': 'missing',
                'turbidity': 'missing',
                'ph': 'unassessed',
                'do': 'unassessed',
            },
        }

    score = 100
    problems = []
    recommendations = []
    parameter_status = {}

    # --- Temperature ---
    if temperature is not None and not math.isnan(temperature):
        r = WATER_QUALITY_RANGES['temperature']
        if temperature < r['ideal_min']:
            score -= r['penalty']
            problems.append(
                r['problem_template'].format(
                    status="below preferred range",
                    value=temperature
                )
            )
            recommendations.append(r['recommendation'])
            parameter_status['temperature'] = 'out_of_range'
        elif temperature > r['ideal_max']:
            score -= r['penalty']
            problems.append(
                r['problem_template'].format(
                    status="above preferred range",
                    value=temperature
                )
            )
            recommendations.append(r['recommendation'])
            parameter_status['temperature'] = 'out_of_range'
        else:
            parameter_status['temperature'] = 'normal'
    else:
        parameter_status['temperature'] = 'missing'

    # --- Turbidity ---
    if turbidity is not None and not math.isnan(turbidity):
        r = WATER_QUALITY_RANGES['turbidity']
        if turbidity > r['severe_max']:
            score -= r['penalty_severe']
            problems.append(
                r['problem_template_severe'].format(value=turbidity)
            )
            recommendations.append(r['recommendation_severe'])
            parameter_status['turbidity'] = 'severe'
        elif turbidity > r['moderate_max']:
            score -= r['penalty_moderate']
            problems.append(
                r['problem_template_moderate'].format(value=turbidity)
            )
            recommendations.append(r['recommendation_moderate'])
            parameter_status['turbidity'] = 'moderate'
        else:
            parameter_status['turbidity'] = 'normal'
    else:
        parameter_status['turbidity'] = 'missing'

    # --- TDS ---
    if tds is not None and not math.isnan(tds):
        r = WATER_QUALITY_RANGES['tds']
        if tds > r['severe_max']:
            score -= r['penalty_severe']
            problems.append(
                r['problem_template_severe'].format(value=tds)
            )
            recommendations.append(r['recommendation_severe'])
            parameter_status['tds'] = 'severe'
        elif tds > r['moderate_max']:
            score -= r['penalty_moderate']
            problems.append(
                r['problem_template_moderate'].format(value=tds)
            )
            recommendations.append(r['recommendation_moderate'])
            parameter_status['tds'] = 'moderate'
        else:
            parameter_status['tds'] = 'normal'
    else:
        parameter_status['tds'] = 'missing'

    # --- Predicted pH ---
    if predicted_ph is not None and not math.isnan(predicted_ph):
        r = WATER_QUALITY_RANGES['ph']
        if predicted_ph < r['ideal_min']:
            score -= r['penalty']
            problems.append(
                r['problem_template'].format(
                    status="below preferred range",
                    value=predicted_ph
                )
            )
            recommendations.append(r['recommendation_low'])
            parameter_status['ph'] = 'out_of_range'
        elif predicted_ph > r['ideal_max']:
            score -= r['penalty']
            problems.append(
                r['problem_template'].format(
                    status="above preferred range",
                    value=predicted_ph
                )
            )
            recommendations.append(r['recommendation_high'])
            parameter_status['ph'] = 'out_of_range'
        else:
            parameter_status['ph'] = 'normal'
    else:
        parameter_status['ph'] = 'unassessed'

    # --- Predicted DO ---
    if predicted_do is not None and not math.isnan(predicted_do):
        r = WATER_QUALITY_RANGES['do']
        if predicted_do < r['critical_min']:
            score -= r['penalty_critical']
            problems.append(
                r['problem_template_critical'].format(value=predicted_do)
            )
            recommendations.append(r['recommendation_critical'])
            parameter_status['do'] = 'critical'
        elif predicted_do < r['low_min']:
            score -= r['penalty_low']
            problems.append(
                r['problem_template_low'].format(value=predicted_do)
            )
            recommendations.append(r['recommendation_low'])
            parameter_status['do'] = 'low'
        else:
            parameter_status['do'] = 'normal'
    else:
        parameter_status['do'] = 'unassessed'

    # Default positive recommendation if no issues detected
    if len(problems) == 0:
        recommendations.append(
            "All monitored water quality parameters are within optimal ranges. Maintain current habitat conditions."
        )

    # Clamp score to 0–100
    score = max(0, min(100, score))

    # Exact boundary classification
    if score >= 80:
        category = "Excellent"
    elif score >= 60:
        category = "Good"
    elif score >= 40:
        category = "Moderate"
    else:
        category = "Poor"

    is_complete = (
        temperature is not None and
        tds is not None and
        turbidity is not None and
        predicted_ph is not None and
        predicted_do is not None
    )

    return {
        'hss': score,
        'category': category,
        'is_complete': is_complete,
        'problems': problems,
        'recommendations': recommendations,
        'parameter_status': parameter_status,
    }


# ============================================================
# STATIC FILE ROUTES
# ============================================================

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


# ============================================================
# API: LATEST WATER QUALITY DATA
# ============================================================

@app.route('/api/latest')
def api_latest():
    """
    Fetch latest sensor data from Firebase, run ML predictions,
    compute habitat assessment, and return a structured response.
    """
    try:
        # --- Fetch from Firebase ---
        try:
            firebase_response = requests.get(
                FIREBASE_LATEST_URL, timeout=10
            )
        except (requests.exceptions.RequestException, IOError, Exception) as e:
            logger.error("Firebase connection failed: %s", e)
            return jsonify({
                "success": False,
                "error": "Firebase connection failed",
                "details": str(e),
            }), 502

        if firebase_response.status_code != 200:
            return jsonify({
                "success": False,
                "error": f"Firebase returned HTTP {firebase_response.status_code}",
            }), 502

        data = firebase_response.json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No sensor data available in Firebase",
            }), 404

        # --- Extract sensor values ---
        temperature = data.get('temperature')
        tds = data.get('tds')
        turbidity = data.get('turbidity')

        # Timestamp handling
        # ESP32 sends uptimeMs but not a real timestamp.
        # We use the server receive time as the reference.
        sensor_timestamp = data.get('timestamp') or data.get('time')
        server_time = datetime.now(timezone.utc).isoformat()

        # Staleness check
        is_stale = False
        stale_reason = None
        now_ts = datetime.now(timezone.utc).timestamp()

        # 1. Check uptimeMs freeze from ESP32 node
        uptime_ms = data.get('uptimeMs')
        if uptime_ms is not None:
            if _device_tracker['last_uptime_ms'] is None or _device_tracker['last_uptime_ms'] != uptime_ms:
                _device_tracker['last_uptime_ms'] = uptime_ms
                _device_tracker['last_change_time'] = now_ts
            elif _device_tracker['last_change_time'] is not None:
                frozen_duration = now_ts - _device_tracker['last_change_time']
                if frozen_duration > STALE_THRESHOLD_SECONDS:
                    is_stale = True
                    stale_reason = (
                        f"ESP32 uptime has frozen at {uptime_ms}ms for {int(frozen_duration)}s "
                        f"(stale threshold: {STALE_THRESHOLD_SECONDS}s)"
                    )

        # 2. Check explicit timestamp if present
        if sensor_timestamp:
            try:
                if isinstance(sensor_timestamp, (int, float)):
                    if sensor_timestamp > 1e11:  # Epoch milliseconds
                        ts_sec = sensor_timestamp / 1000.0
                    else:  # Epoch seconds
                        ts_sec = float(sensor_timestamp)
                elif isinstance(sensor_timestamp, str):
                    dt = datetime.fromisoformat(sensor_timestamp.replace('Z', '+00:00'))
                    ts_sec = dt.timestamp()
                else:
                    ts_sec = None

                if ts_sec is not None:
                    age_seconds = now_ts - ts_sec
                    if age_seconds > STALE_THRESHOLD_SECONDS:
                        is_stale = True
                        stale_reason = (
                            f"Sensor data timestamp is {int(age_seconds)}s old "
                            f"(stale threshold: {STALE_THRESHOLD_SECONDS}s)"
                        )
            except Exception as e:
                logger.warning("Could not parse timestamp '%s': %s", sensor_timestamp, e)

        # --- Build base response ---
        result = {
            "success": True,
            "timestamp": sensor_timestamp,
            "server_time": server_time,
            "is_stale": is_stale,
            "stale_reason": stale_reason,
            "device": data.get('device_id', 'ESP32_01'),
            "sensor_data": {
                "temperature": temperature,
                "tds": tds,
                "turbidity": turbidity,
            },
            "predictions": {
                "ph": None,
                "do": None,
            },
            "prediction_status": "pending",
            "prediction_details": None,
            "assessment": {
                "hss": None,
                "category": "Unavailable",
                "is_complete": False,
                "problems": [],
                "recommendations": [],
            },
            "conversion_info": None,
            "message": "",
            # Backward compat
            "ml_prediction": {
                "available": False,
                "ph": None,
                "do": None,
                "status": "Waiting for valid inputs",
            },
            "raw_data": data,
        }

        # Merge raw data for backward compatibility
        for k, v in data.items():
            if k not in result:
                result[k] = v

        # --- Validate required sensor inputs ---
        missing = []
        if temperature is None:
            missing.append("temperature")
        if turbidity is None:
            missing.append("turbidity")
        if tds is None:
            missing.append("tds")

        if missing:
            result["prediction_status"] = "missing_inputs"
            result["message"] = (
                f"Missing required sensor readings: {', '.join(missing)}"
            )
            result["ml_prediction"]["status"] = result["message"]
            result["assessment"] = compute_habitat_assessment(None, None, None)
            return jsonify(result)

        # --- Validate finite numbers for ML predictions ---
        try:
            temp_val = float(temperature)
            tds_val = float(tds)
            turb_val = float(turbidity)
        except (ValueError, TypeError):
            result["prediction_status"] = "invalid_inputs"
            result["message"] = "Sensor values are not valid numbers."
            result["ml_prediction"]["status"] = result["message"]
            result["assessment"] = compute_habitat_assessment(None, None, None)
            return jsonify(result)

        if any(math.isnan(v) or math.isinf(v) for v in (temp_val, tds_val, turb_val)):
            result["prediction_status"] = "invalid_inputs"
            result["message"] = "Sensor values must be finite numbers (NaN/Inf not allowed)."
            result["ml_prediction"]["status"] = result["message"]
            result["assessment"] = compute_habitat_assessment(None, None, None)
            return jsonify(result)

        prediction = predict_water_quality(temp_val, tds_val, turb_val)

        if prediction['success']:
            ph_pred = prediction['ph']
            do_pred = prediction['do']

            result["predictions"]["ph"] = ph_pred
            result["predictions"]["do"] = do_pred
            result["prediction_status"] = "success"
            result["prediction_details"] = {
                "model": "Gradient Boosting Regressor",
                "input_warnings": prediction.get('input_warnings', []),
                "sp_conductance_estimated": prediction.get(
                    'sp_conductance_estimated'
                ),
            }
            result["conversion_info"] = {
                "tds_ppm": tds_val,
                "sp_conductance_estimated_ms_cm": prediction.get(
                    'sp_conductance_estimated'
                ),
                "conversion_factor": prediction.get('conversion_factor'),
                "is_approximate": True,
                "warning": prediction.get('conversion_warning'),
            }
            result["message"] = (
                "Water quality assessment generated. "
                "Note: pH and DO predictions use an approximate "
                "TDS-to-conductance conversion."
            )

            # Backward compat
            result["ml_prediction"]["available"] = True
            result["ml_prediction"]["ph"] = ph_pred
            result["ml_prediction"]["do"] = do_pred
            result["ml_prediction"]["status"] = (
                "Predicted using Gradient Boosting "
                "(TDS→conductance conversion applied)"
            )

            # --- Compute full assessment ---
            assessment = compute_habitat_assessment(
                temp_val, tds_val, turb_val,
                predicted_ph=ph_pred,
                predicted_do=do_pred
            )
            result["assessment"] = assessment

        else:
            result["prediction_status"] = "error"
            result["message"] = prediction.get(
                'error', 'Prediction failed'
            )
            result["ml_prediction"]["status"] = result["message"]

            # Compute partial assessment without ML predictions
            assessment = compute_habitat_assessment(
                temp_val, tds_val, turb_val
            )
            result["assessment"] = assessment

        return jsonify(result)

    except Exception as e:
        logger.exception("Unexpected error in /api/latest")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ============================================================
# API: HISTORY
# ============================================================

@app.route('/api/history')
def api_history():
    """Proxy Firebase history data."""
    try:
        response = requests.get(FIREBASE_HISTORY_URL, timeout=15)
        if response.status_code != 200:
            return jsonify({
                "success": False,
                "error": "Firebase unavailable",
            }), 502
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({
            "success": False,
            "error": f"Firebase connection failed: {e}",
        }), 502
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ============================================================
# API: INTERVENTION SIMULATOR
# ============================================================

@app.route('/api/simulate', methods=['POST'])
def api_simulate():
    """
    Run a what-if simulation.

    Accepts modified sensor values and optional conversion_factor,
    runs ML predictions, and returns the simulated assessment
    alongside predictions.

    Does NOT modify Firebase data.
    """
    try:
        body = request.get_json(silent=True)

        if not body:
            return jsonify({
                "success": False,
                "error": "Request body is required (JSON)",
            }), 400

        sim_temp = body.get('temperature')
        sim_tds = body.get('tds')
        sim_turb = body.get('turbidity')
        custom_factor = body.get('conversion_factor')

        # Validate presence
        missing = []
        if sim_temp is None:
            missing.append('temperature')
        if sim_tds is None:
            missing.append('tds')
        if sim_turb is None:
            missing.append('turbidity')

        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing parameters: {', '.join(missing)}",
            }), 400

        try:
            sim_temp = float(sim_temp)
            sim_tds = float(sim_tds)
            sim_turb = float(sim_turb)
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "All parameters must be valid numbers.",
            }), 400

        if any(math.isnan(v) or math.isinf(v) for v in (sim_temp, sim_tds, sim_turb)):
            return jsonify({
                "success": False,
                "error": "Simulated values must be finite numbers (NaN/Inf not allowed).",
            }), 400

        factor_arg = None
        if custom_factor is not None:
            try:
                factor_arg = float(custom_factor)
                if factor_arg < 0.25 or factor_arg > 1.25 or math.isnan(factor_arg):
                    return jsonify({
                        "success": False,
                        "error": "conversion_factor must be between 0.25 and 1.25",
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": "conversion_factor must be numeric",
                }), 400

        # Run prediction on simulated values
        prediction = predict_water_quality(
            sim_temp, sim_tds, sim_turb,
            conversion_factor=factor_arg
        )

        sim_ph = prediction['ph'] if prediction['success'] else None
        sim_do = prediction['do'] if prediction['success'] else None

        # Compute simulated assessment
        assessment = compute_habitat_assessment(
            sim_temp, sim_tds, sim_turb,
            predicted_ph=sim_ph,
            predicted_do=sim_do
        )

        return jsonify({
            "success": True,
            "simulated": True,
            "input": {
                "temperature": sim_temp,
                "tds": sim_tds,
                "turbidity": sim_turb,
            },
            "predictions": {
                "ph": sim_ph,
                "do": sim_do,
            },
            "prediction_success": prediction['success'],
            "prediction_error": prediction.get('error'),
            "assessment": assessment,
            "conversion_info": {
                "sp_conductance_estimated": prediction.get(
                    'sp_conductance_estimated'
                ),
                "conversion_factor": prediction.get('conversion_factor'),
                "is_approximate": True,
                "warning": prediction.get('conversion_warning'),
            },
            "message": (
                "Simulated values — not saved to Firebase. "
                "These do not affect actual sensor readings."
            ),
        })

    except Exception as e:
        logger.exception("Error in /api/simulate")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ============================================================
# API: CALIBRATION & CONVERSION CONFIGURATION
# ============================================================

@app.route('/api/config/conversion-factor', methods=['GET', 'POST'])
def api_conversion_factor():
    """
    Get or configure the TDS-to-conductance conversion factor.

    GET: Returns current active factor and ecological guidelines.
    POST: Updates conversion factor with {"factor": float}.
    """
    if request.method == 'POST':
        body = request.get_json(silent=True)
        if not body or 'factor' not in body:
            return jsonify({
                "success": False,
                "error": "JSON body with 'factor' is required",
            }), 400
        try:
            updated = set_tds_conversion_factor(body['factor'])
            return jsonify({
                "success": True,
                "conversion_factor": updated,
                "message": f"Conversion factor updated to {updated}",
            })
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": str(e),
            }), 400

    return jsonify({
        "success": True,
        "conversion_factor": get_tds_conversion_factor(),
        "default_factor": 0.55,
        "valid_range": [0.25, 1.25],
        "guidelines": {
            "0.50": "NaCl standard / laboratory calibration solution",
            "0.55": "Mixed freshwater baseline (general approximation)",
            "0.65": "Sulfate-rich waters / mineralized streams",
            "0.70": "High calcium carbonate / alkaline water bodies",
        },
        "scientific_note": (
            "Training dataset KLGO has only specific conductance (mS/cm). "
            "No paired TDS measurements exist. On-site calibration is recommended."
        ),
    })


# ============================================================
# API: MODEL STATUS
# ============================================================

@app.route('/api/model-status')
def api_model_status():
    """Return the current ML model loading status."""
    status = get_model_status()
    return jsonify({
        "success": True,
        "models": status,
        "conversion_factor": get_tds_conversion_factor(),
    })


# ============================================================
# CATCH-ALL STATIC FILES (REGISTERED AFTER ALL API ROUTES)
# ============================================================

@app.route('/<path:path>')
def static_files(path):
    """Serve frontend static files; explicitly block hijacking /api/* routes."""
    if path.startswith('api/'):
        return jsonify({"success": False, "error": f"API endpoint '/{path}' not found"}), 404
    return send_from_directory(app.static_folder, path)


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("AI Aquatic Habitat Assessment System")
    logger.info("=" * 50)

    # Pre-load models on startup
    if load_models():
        logger.info("ML models loaded successfully on startup.")
    else:
        status = get_model_status()
        logger.warning(
            "ML models failed to load: %s", status.get('error')
        )

    logger.info("Starting Flask server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)
