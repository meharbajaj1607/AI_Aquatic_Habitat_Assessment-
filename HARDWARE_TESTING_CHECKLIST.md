# Hardware Testing & Physical Verification Checklist
**AI-Based Aquatic Habitat Assessment System — Hardware Engineering Readiness Guide**

---

## 1. System Bill of Materials (BOM) & Component Specifications

| Item | Component Description | Interface / Protocol | Operating Voltage | Current Consumption | Critical Notes |
|---|---|---|---|---|---|
| **1** | ESP32 DevKit V1 (30-pin or 38-pin) | Dual-core Tensilica, 2.4 GHz Wi-Fi | 5V (USB) or 3.3V | 80 mA avg, 400 mA peak | Wi-Fi TX causes voltage dips if USB power is weak. |
| **2** | DS18B20 Waterproof Probe | OneWire Bus | 3.0V – 5.5V | 1.5 mA active | **Requires 4.7kΩ pull-up resistor** between DQ and 3.3V. |
| **3** | DFRobot Gravity Analog TDS Sensor | Analog Voltage Output | 3.3V – 5.5V | 3 – 6 mA | Output voltage range: 0 – 2.3V. Waterproof probe. |
| **4** | Optical Turbidity Sensor (TS-300B / Gravity) | Analog Voltage Output | 5.0V (VCC required) | 30 – 40 mA | **Warning: Output reaches 4.2V–4.5V in clear water. Exceeds ESP32 3.3V ADC limit.** |
| **5** | Resistors (Signal Conditioning) | Carbon film / Metal film | — | — | 1x 4.7kΩ (OneWire pull-up); 1x 10kΩ & 1x 20kΩ (Voltage divider for Turbidity). |
| **6** | Decoupling Capacitors | Ceramic disc | 16V / 25V | — | 2x 0.1µF (100nF) across ADC inputs to GND to suppress Wi-Fi RF noise. |
| **7** | Breadboard / Protoboard & Jumper Wires | Solid core / Dupont | — | — | Verify solid ground connections. |

---

## 2. Complete Wiring Table & Pin Discrepancy Alert

> [!WARNING]
> ### CRITICAL PIN ASSIGNMENT INCONSISTENCY IDENTIFIED
> * In **Firmware (`mehar.ino`) lines 61–63:**
>   * `TDS_PIN` is mapped to **GPIO 34**
>   * `TURBIDITY_PIN` is mapped to **GPIO 35**
> * In the **Physical Hardware Test Plan:**
>   * `TDS` is expected on **GPIO 35**
>   * `Turbidity` is expected on **GPIO 34**
>
> **Action Required Before Powering On:** You must align physical wiring to firmware or update firmware `#define` constants. If swapped, the non-linear TDS cubic equation will be applied to the turbidity sensor voltage, and TDS will receive optical voltage, resulting in completely invalid readings.

### Recommended Wiring Reference (Based on Firmware `mehar.ino` Defaults)

| Sensor Pin | ESP32 Pin | Signal Type | Electrical Requirement |
|---|---|---|---|
| **DS18B20 VDD (Red)** | `3.3V` | DC Power | 3.3V Power Rail |
| **DS18B20 GND (Black)** | `GND` | Power Ground | Common Ground Rail |
| **DS18B20 Data / DQ (Yellow)** | `GPIO 4` | Digital OneWire | **4.7kΩ pull-up resistor to 3.3V** |
| **TDS VCC (+)** | `5V` or `3.3V` | DC Power | 3.3V recommended to ensure 0–2.3V output |
| **TDS GND (-)** | `GND` | Power Ground | Common Ground Rail |
| **TDS Signal (A)** | `GPIO 34` (ADC1_CH6) | Analog Input (0–2.3V) | Optional 0.1µF capacitor to GND for filtering |
| **Turbidity VCC (+)** | `5V` (VIN) | DC Power | Optical sensor requires 5V for infrared LED emission |
| **Turbidity GND (-)** | `GND` | Power Ground | Common Ground Rail |
| **Turbidity Signal (A)** | `GPIO 35` (ADC1_CH7) | Analog Input | **MUST USE VOLTAGE DIVIDER** (2/3 attenuation) |

### Turbidity Voltage Divider Circuit (5V Protection)
```text
Turbidity Sensor Output (0 – 4.5V)
           │
         [10 kΩ]
           │
           ├─── ESP32 GPIO 35 (Max ~3.0V safe input)
           │
         [20 kΩ]
           │
          GND
```

---

## 3. Power Requirements & Electrical Integrity

1. **Power Supply Capacity:**
   * ESP32 Wi-Fi transmission bursts draw up to **400 mA** peak current.
   * Total system consumption with all sensors active: $\approx 480\text{ mA}$.
   * **Rule:** Do not power the system from a low-current USB hub or computer unpowered port. Use a dedicated 5V 1.0A or 2.0A USB power supply.
2. **ADC Ground Reference:**
   * Analog measurements are measured relative to the ESP32 GND pin. If breadboard jumper wires introduce ground resistance, current spikes from the Wi-Fi modem will cause voltage drops across GND, leading to shifting ADC counts. Ensure a dedicated ground bus.

---

## 4. Step-by-Step Hardware Verification Procedure

### Stage 1: Power & Bus Verification (Dry Bench Test)
* [ ] Disconnect all sensors from GPIOs.
* [ ] Connect ESP32 to USB. Measure 3.3V rail with a multimeter (must be between 3.25V and 3.35V).
* [ ] Measure 5V (VIN) rail (must be between 4.8V and 5.2V).
* [ ] Verify multimeter continuity on common ground rails.

### Stage 2: Individual Sensor Testing

#### A. Temperature Sensor (DS18B20)
* [ ] Wire DS18B20 with 4.7kΩ pull-up between DQ (GPIO 4) and 3.3V.
* [ ] Flash `mehar.ino`. Open Serial Monitor at 115200 baud.
* [ ] **Expected Observation:** Serial Monitor displays ambient temperature ($20\text{--}28^\circ\text{C}$).
* [ ] **Failure Mode:** If `-127.00 °C` appears, OneWire communication has failed (missing pull-up, loose wire, or reversed VDD/GND).
* [ ] **Response Test:** Hold sensor tip between fingers. Temperature should rise steadily toward $32\text{--}35^\circ\text{C}$.

#### B. Total Dissolved Solids (TDS) Sensor
* [ ] Connect TDS probe to GPIO 34.
* [ ] **Dry Probe Test:** Leave probe in air.
  * Expected: `ADC: ~0`, `Voltage: 0.000 V`, `TDS: 0.0 ppm`.
* [ ] **Tap Water Test:** Submerge probe into tap water.
  * Expected: `ADC: 400 – 1200`, `Voltage: 0.3V – 0.9V`, `TDS: 80 – 350 ppm`.
* [ ] **Standard Solution Test:** Submerge probe in $1413\text{ }\mu\text{S/cm}$ KCl standard solution.
  * Adjust `TDS_CALIBRATION_FACTOR` in firmware so reported TDS matches standard value ($\approx 706\text{ ppm}$ at $K=0.5$).

#### C. Optical Turbidity Sensor
* [ ] Connect Turbidity analog output through voltage divider to GPIO 35.
* [ ] **Clear Water Test:** Submerge sensor head in clean distilled water.
  * Expected: Output voltage is at maximum ($\approx 3.8\text{V} - 4.2\text{V}$ before divider, $\approx 2.5\text{V} - 2.8\text{V}$ at GPIO).
  * Check serial output for raw ADC reading.
* [ ] **Turbid Water Test:** Add a drop of milk or soil to water and stir.
  * Expected: Output voltage drops substantially ($\approx 1.2\text{V} - 1.8\text{V}$ before divider).
  * Note: In `mehar.ino`, ensure baseline voltage calibration matches the clean water voltage.

---

## 5. End-to-End Pipeline Verification

```text
[ESP32 Node] ──(Wi-Fi HTTPS PUT)──> [Firebase RTDB] ──(REST GET)──> [Flask Backend] ──(WebSockets/HTTP)──> [Dashboard]
```

1. **Wi-Fi & Firebase Connectivity:**
   * [ ] Update `WIFI_SSID` and `WIFI_PASSWORD` in `mehar.ino`.
   * [ ] Verify ESP32 connects to local Wi-Fi router and prints local IP address.
   * [ ] Confirm serial output prints: `>>> Firebase upload successful.`
2. **Cloud RTDB Check:**
   * [ ] Open Firebase Console in browser: `https://console.firebase.google.com/`
   * [ ] Inspect `/sensorData/latest.json`. Confirm `temperature`, `tds`, `turbidity`, and `uptimeMs` update every 10 seconds.
3. **Flask Backend Ingestion:**
   * [ ] Run `python backend/app.py`.
   * [ ] Open `http://localhost:5000/api/latest` in browser.
   * [ ] Verify JSON returns `success: true`, `is_stale: false`, ML predictions for `ph` and `do`, and an active HSS score.
4. **Dashboard Visualization:**
   * [ ] Open `http://localhost:5000/`.
   * [ ] Verify HSS radial gauge displays current score.
   * [ ] Verify Live Monitoring tiles show temperature, TDS, and turbidity.
   * [ ] Test What-If Simulator: Adjust slider, click "Run Simulation", verify simulated purple card updates without affecting live telemetry.

---

## 6. Common Errors & Troubleshooting

| Symptom | Root Cause | Engineering Solution |
|---|---|---|
| Temperature reads `-127.00 °C` | OneWire pull-up resistor missing or wire disconnected. | Install 4.7kΩ resistor between GPIO 4 and 3.3V. Check wiring continuity. |
| TDS reads `0.0 ppm` in water | Probe pin mapped to wrong GPIO or sensor unpowered. | Verify if TDS is wired to GPIO 34 vs 35. Confirm VCC is active. |
| Turbidity reading stays at maximum | Sensor output inverted or baseline voltage uncalibrated. | Calibrate `TURBIDITY_BASELINE_VOLTAGE` in distilled water. |
| ESP32 crashes / boot-loops during Wi-Fi connection | Power supply current dip when radio turns on. | Use an external 5V 2A USB power supply. Add a 100µF electrolytic capacitor across 5V and GND. |
| Firebase returns `HTTP 401 Unauthorized` | Firebase Database security rules require authentication. | Set Realtime Database rules to allow read/write during testing, or generate a database secret. |
| Backend marks data as stale immediately | ESP32 uptimeMs has frozen or server clock mismatch. | Check ESP32 Serial Monitor to ensure loop is executing and updating `uptimeMs`. |
