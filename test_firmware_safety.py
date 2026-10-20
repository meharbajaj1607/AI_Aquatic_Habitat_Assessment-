"""
=============================================================
AI AQUATIC HABITAT ASSESSMENT
Firmware Safety & Hardware Readiness Verification Test Suite
=============================================================

Tests:
1. Valid DS18B20 temperature reading & TDS compensation.
2. Disconnected DS18B20 (-127°C / DEVICE_DISCONNECTED_C) detection & fallback.
3. Invalid temperature handling (85°C unready scratchpad, NaN, sub-zero limits).
4. Prevention of corrupted negative / zero TDS readings.
5. Exact firmware JSON payload generation & RFC 8259 validity.
6. Flask backend ingestion compatibility with new validity fields.
=============================================================
"""

import math
import json
import os
import sys
from unittest.mock import patch, MagicMock

# UTF-8 stdout encoding for Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

DEVICE_DISCONNECTED_C = -127.0
ADC_REFERENCE = 3.3
ADC_MAX = 4095
TDS_CALIBRATION_FACTOR = 1.00
TDS_OFFSET = 0.0

# -----------------------------------------------------------
# Python simulation of the exact C++ firmware logic in mehar.ino
# -----------------------------------------------------------

def simulate_firmware_read_sensors(raw_temp_c, tds_adc, turbidity_adc=2500):
    """
    Exact simulation of void readSensors(...) in mehar.ino
    """
    # 1. TDS Voltage
    tds_voltage = tds_adc * ADC_REFERENCE / ADC_MAX

    # 2. Temperature & validity check
    if (
        raw_temp_c == DEVICE_DISCONNECTED_C
        or raw_temp_c <= -100.0
        or raw_temp_c < -5.0
        or raw_temp_c >= 85.0
        or math.isnan(raw_temp_c)
    ):
        temp_valid = False
        temperature_c = raw_temp_c
    else:
        temp_valid = True
        temperature_c = raw_temp_c

    # 3. TDS Temperature Compensation
    # If invalid, fallback to 25.0°C reference
    comp_temp = temperature_c if temp_valid else 25.0
    compensation_coefficient = 1.0 + 0.02 * (comp_temp - 25.0)
    compensated_voltage = tds_voltage / compensation_coefficient

    # 4. TDS Polynomial Estimation
    tds_ppm = (
        133.42 * (compensated_voltage ** 3)
        - 255.86 * (compensated_voltage ** 2)
        + 857.39 * compensated_voltage
    ) * 0.5
    tds_ppm = tds_ppm * TDS_CALIBRATION_FACTOR + TDS_OFFSET
    if tds_ppm < 0:
        tds_ppm = 0.0

    # 5. Turbidity
    turbidity_voltage = turbidity_adc * ADC_REFERENCE / ADC_MAX
    baseline = 0.000
    corrected_turb_v = max(0.0, turbidity_voltage - baseline)
    turbidity_estimate = corrected_turb_v * 1000.0 * 1.00
    if turbidity_estimate < 0:
        turbidity_estimate = 0.0

    return {
        'temperatureC': temperature_c,
        'tempValid': temp_valid,
        'tdsADC': tds_adc,
        'tdsVoltage': tds_voltage,
        'tdsPPM': tds_ppm,
        'compensationCoefficient': compensation_coefficient,
        'compensatedVoltage': compensated_voltage,
        'turbidityADC': turbidity_adc,
        'turbidityVoltage': turbidity_voltage,
        'turbidityEstimate': turbidity_estimate,
    }


def simulate_firmware_json_payload(sensor_data, wifi_rssi=-62, uptime_ms=45230):
    """
    Exact simulation of String json in sendToFirebase(...) in mehar.ino
    """
    temp_valid = sensor_data['tempValid']
    temp_c = sensor_data['temperatureC']

    parts = ["{"]

    if temp_valid:
        parts.append(f'"temperature":{temp_c:.2f}')
    else:
        parts.append('"temperature":null')

    parts.append(f',"tempValid":{"true" if temp_valid else "false"}')
    parts.append(f',"temp_valid":{"true" if temp_valid else "false"}')
    parts.append(f',"temperatureStatus":"{"valid" if temp_valid else "disconnected_or_invalid"}"')

    parts.append(f',"tds":{sensor_data["tdsPPM"]:.2f}')
    parts.append(f',"tdsADC":{sensor_data["tdsADC"]:.0f}')
    parts.append(f',"tdsVoltage":{sensor_data["tdsVoltage"]:.3f}')

    parts.append(f',"turbidity":{sensor_data["turbidityEstimate"]:.2f}')
    parts.append(f',"turbidityADC":{sensor_data["turbidityADC"]:.0f}')
    parts.append(f',"turbidityVoltage":{sensor_data["turbidityVoltage"]:.3f}')

    parts.append(',"ph":null')
    parts.append(',"dissolvedOxygen":null')
    parts.append(f',"wifiRSSI":{wifi_rssi}')
    parts.append(f',"uptimeMs":{uptime_ms}')

    if temp_valid:
        parts.append(',"tdsStatus":"estimated"')
    else:
        parts.append(',"tdsStatus":"estimated_temp_fallback"')

    parts.append(',"turbidityStatus":"prototype_estimate"')
    parts.append(',"phStatus":"sensor_not_installed"')
    parts.append(',"doStatus":"sensor_not_installed"')
    parts.append("}")

    return "".join(parts)


# -----------------------------------------------------------
# Test Runner
# -----------------------------------------------------------

test_results = []

def record_test(name, condition, detail=""):
    test_results.append({'name': name, 'passed': bool(condition), 'detail': str(detail)})
    status = "[PASS]" if condition else "[FAIL]"
    print(f"  {status} {name}" + (f" - {detail}" if detail else ""))


print("=" * 65)
print("  FIRMWARE SAFETY & HARDWARE READINESS TEST SUITE")
print("=" * 65)

# --- Group 1: Valid Temperature Readings ---
print("\n--- Group 1: Valid DS18B20 Temperature Handling ---")
r_valid = simulate_firmware_read_sensors(raw_temp_c=24.5, tds_adc=1500)
record_test("Valid temperature 24.5°C flagged as tempValid=True", r_valid['tempValid'] is True)
record_test("Valid temperature compensation coefficient close to 0.99", abs(r_valid['compensationCoefficient'] - 0.99) < 0.001)
record_test("TDS reading is non-zero and plausible", r_valid['tdsPPM'] > 100.0, f"{r_valid['tdsPPM']:.1f} ppm")

# --- Group 2: Disconnected DS18B20 Detection (-127°C) ---
print("\n--- Group 2: Disconnected DS18B20 Detection (-127°C) ---")
r_disc = simulate_firmware_read_sensors(raw_temp_c=DEVICE_DISCONNECTED_C, tds_adc=1500)
record_test("Disconnected probe (-127°C) flagged as tempValid=False", r_disc['tempValid'] is False)
record_test("Compensation coefficient falls back to exactly 1.0 (25°C ref)", r_disc['compensationCoefficient'] == 1.0)
record_test("TDS reading remains valid and positive (NOT 0 ppm)", r_disc['tdsPPM'] > 100.0, f"{r_disc['tdsPPM']:.1f} ppm")

# Verify what would have happened under OLD firmware
old_bad_coeff = 1.0 + 0.02 * (-127.0 - 25.0)  # -2.04
old_bad_v = (1500 * 3.3 / 4095) / old_bad_coeff
old_bad_tds = max(0.0, (133.42 * (old_bad_v**3) - 255.86 * (old_bad_v**2) + 857.39 * old_bad_v) * 0.5)
record_test("Old firmware corrupted calculation produced silent 0.0 ppm", old_bad_tds == 0.0)
record_test("New firmware successfully prevents silent 0 ppm corruption", r_disc['tdsPPM'] > 0.0 and r_disc['tdsPPM'] != old_bad_tds)

# --- Group 3: Out-of-Bounds & Invalid Temperature Handling ---
print("\n--- Group 3: Invalid Temperature Boundary Handling ---")
for bad_temp, desc in [
    (85.0, "DS18B20 power-on reset state (+85°C)"),
    (92.0, "Extreme scalding temperature (+92°C)"),
    (-10.0, "Sub-zero ice reading (-10°C)"),
    (-127.0, "Bus disconnect code (-127°C)"),
    (float('nan'), "NaN reading from sensor error"),
]:
    r_bad = simulate_firmware_read_sensors(raw_temp_c=bad_temp, tds_adc=1200)
    record_test(f"{desc} flagged as tempValid=False", r_bad['tempValid'] is False)
    record_test(f"{desc} uses 25°C reference (coeff=1.0)", r_bad['compensationCoefficient'] == 1.0)
    record_test(f"{desc} maintains valid TDS (>0)", r_bad['tdsPPM'] > 50.0)

# --- Group 4: JSON Payload RFC 8259 Validity ---
print("\n--- Group 4: JSON Payload Formatting & Compliance ---")
json_valid = simulate_firmware_json_payload(r_valid)
parsed_valid = json.loads(json_valid)
record_test("Valid payload parses as valid JSON", parsed_valid is not None)
record_test("Valid payload temperature is numeric", isinstance(parsed_valid['temperature'], (int, float)))
record_test("Valid payload tempValid is true", parsed_valid['tempValid'] is True)
record_test("Valid payload temp_valid is true", parsed_valid['temp_valid'] is True)
record_test("Valid payload temperatureStatus is 'valid'", parsed_valid['temperatureStatus'] == 'valid')
record_test("Valid payload tdsStatus is 'estimated'", parsed_valid['tdsStatus'] == 'estimated')

json_disc = simulate_firmware_json_payload(r_disc)
parsed_disc = json.loads(json_disc)
record_test("Disconnected payload parses as valid JSON", parsed_disc is not None)
record_test("Disconnected payload temperature is null (None)", parsed_disc['temperature'] is None)
record_test("Disconnected payload tempValid is false", parsed_disc['tempValid'] is False)
record_test("Disconnected payload temp_valid is false", parsed_disc['temp_valid'] is False)
record_test("Disconnected payload temperatureStatus is 'disconnected_or_invalid'", parsed_disc['temperatureStatus'] == 'disconnected_or_invalid')
record_test("Disconnected payload tdsStatus is 'estimated_temp_fallback'", parsed_disc['tdsStatus'] == 'estimated_temp_fallback')

# --- Group 5: Flask Backend Ingestion Compatibility ---
print("\n--- Group 5: Flask Backend Ingestion Compatibility ---")
from backend.app import app

client = app.test_client()

# 5A: Test backend ingestion of valid sensor payload
with patch('backend.app.requests.get') as mock_get:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = parsed_valid
    mock_get.return_value = mock_response

    resp = client.get('/api/latest')
    record_test("Flask GET /api/latest with valid payload returns HTTP 200", resp.status_code == 200)
    body = resp.get_json()
    record_test("Response includes ML predicted pH", body['predictions']['ph'] is not None)
    record_test("Response includes ML predicted DO", body['predictions']['do'] is not None)
    record_test("Response includes HSS assessment", body['assessment']['hss'] is not None)
    record_test("Response passes through tempValid=True", body.get('tempValid') is True)
    record_test("Response passes through temperatureStatus='valid'", body.get('temperatureStatus') == 'valid')

# 5B: Test backend ingestion of disconnected sensor payload (temperature: null)
with patch('backend.app.requests.get') as mock_get:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = parsed_disc
    mock_get.return_value = mock_response

    resp = client.get('/api/latest')
    record_test("Flask GET /api/latest with disconnected payload returns HTTP 200", resp.status_code == 200)
    body = resp.get_json()
    record_test("Backend flags prediction_status as 'missing_inputs'", body['prediction_status'] == 'missing_inputs')
    record_test("Backend message identifies missing temperature", 'temperature' in body['message'])
    record_test("Assessment category is 'Unavailable' without guessing", body['assessment']['category'] == 'Unavailable')
    record_test("Backend preserves tempValid=False in response", body.get('tempValid') is False)
    record_test("Backend preserves temperatureStatus in response", body.get('temperatureStatus') == 'disconnected_or_invalid')
    record_test("Backend preserves fallback TDS reading", body['sensor_data']['tds'] is not None and body['sensor_data']['tds'] > 0)

# Summary
print("\n" + "=" * 65)
passed_count = sum(1 for t in test_results if t['passed'])
total_count = len(test_results)
print(f"  FIRMWARE SAFETY TEST RESULTS: {passed_count}/{total_count} PASSED")
print("=" * 65)

if passed_count != total_count:
    sys.exit(1)
