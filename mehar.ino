/*
============================================================
      AI-BASED AQUATIC HABITAT
      SENSOR NODE - WIFI + FIREBASE
============================================================

Hardware Pin Assignments:
  TDS         -> GPIO 34 (ADC1_CH6, input-only, max 3.3V)
  Turbidity   -> GPIO 35 (ADC1_CH7, input-only, max 3.3V; requires external conditioning if sensor powered by 5V)
  Temperature -> GPIO 4  (OneWire bus, requires 4.7kΩ pull-up to 3.3V)

Firebase:
  Realtime Database

Current sensor availability:
  TDS             -> AVAILABLE (with 25.0°C fallback when temperature is disconnected)
  Turbidity       -> AVAILABLE
  Temperature     -> AVAILABLE (with fault / disconnection detection)
  pH              -> NOT INSTALLED (ML predicted)
  Dissolved Oxygen-> NOT INSTALLED (ML predicted)

Safety & Electrical Notes:
  - DS18B20 1-Wire requires a 4.7kΩ pull-up resistor between GPIO 4 and 3.3V.
  - DS18B20 disconnection (-127°C / DEVICE_DISCONNECTED_C) is detected;
    fallback 25.0°C reference is used for TDS compensation to prevent 0 ppm corruption.
  - Optical turbidity modules powered at 5V output up to ~4.5V in clean water.
    A resistive voltage divider (e.g. 10kΩ / 20kΩ) is mandatory before connecting to GPIO 35.
  - TDS is MODEL-ESTIMATED until reference EC/TDS calibration.
  - Turbidity is a PROTOTYPE ESTIMATE until NTU calibration against Formazin standards.
  - pH and DO are sent as null because those physical probes are not installed.
============================================================
*/


// ============================================================
// LIBRARIES
// ============================================================

#include <WiFi.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>


// ============================================================
// WIFI CONFIGURATION
// ============================================================

const char* WIFI_SSID = "edge 40 neo_1186";
const char* WIFI_PASSWORD = "ot7_borahe";

// Replace both placeholders before uploading. Do not commit real credentials
// to a public repository or share them in screenshots/code snippets.


// ============================================================
// FIREBASE CONFIGURATION
// ============================================================

const char* FIREBASE_HOST =
  "https://aquatic-habitat-system-default-rtdb.asia-southeast1.firebasedatabase.app";


// ============================================================
// SENSOR PINS
// ============================================================

#define TDS_PIN        34
#define TURBIDITY_PIN  35
#define TEMP_PIN       4


// ============================================================
// TEMPERATURE SENSOR
// ============================================================

OneWire oneWire(TEMP_PIN);
DallasTemperature temperatureSensor(&oneWire);


// ============================================================
// CALIBRATION PARAMETERS
// ============================================================

// TDS
float TDS_CALIBRATION_FACTOR = 1.00;
float TDS_OFFSET = 0.0;

// Turbidity
float TURBIDITY_BASELINE_VOLTAGE = 0.000;
float TURBIDITY_CALIBRATION_FACTOR = 1.00;


// ============================================================
// SYSTEM SETTINGS
// ============================================================

const unsigned long SENSOR_INTERVAL = 10000; // 10 seconds

unsigned long lastSensorRead = 0;

// Non-blocking Wi-Fi retry state. WiFi.begin() is called only once per attempt.
const unsigned long WIFI_CONNECT_TIMEOUT = 20000;
const unsigned long WIFI_RETRY_INTERVAL = 15000;
unsigned long wifiAttemptStarted = 0;
unsigned long nextWiFiAttempt = 0;
bool wifiAttemptInProgress = false;


// ============================================================
// ADC SETTINGS
// ============================================================

// 12-bit ADC (0 - 4095) with ADC_11db attenuation covers ~3.3V full-scale.
//
// ELECTRICAL COMPATIBILITY NOTICE:
// ESP32 ADC pins (GPIO 34, 35) tolerate absolute maximum 3.6V (3.3V nominal).
// Direct connection of signals > 3.3V will permanently damage the ESP32.
// Turbidity sensors powered by 5V VCC can output 4.2V - 4.5V in clear water.
// External signal conditioning (e.g., 10kΩ / 20kΩ resistive voltage divider)
// is MANDATORY if sensor output exceeds 3.3V.
// The firmware reads the direct ADC voltage and does NOT assume an external
// divider is pre-installed.
const float ADC_REFERENCE = 3.3;
const int ADC_MAX = 4095;


// ============================================================
// FUNCTION: READ AVERAGE ADC
// ============================================================

float readAverageADC(int pin, int samples = 30)
{
  uint32_t total = 0;
  for (int i = 0; i < samples; i++)
  {
    total += analogRead(pin);
    delay(5);
  }
  return (float)total / samples;
}

// Uses the ESP32 Arduino calibrated millivolt API rather than assuming
// ADC counts map linearly to exactly 3.3 V. Availability depends on the
// installed ESP32 Arduino core version.
float readAverageVoltage(int pin, int samples = 30)
{
  uint32_t totalMilliVolts = 0;
  for (int i = 0; i < samples; i++)
  {
    totalMilliVolts += analogReadMilliVolts(pin);
    delay(5);
  }
  return ((float)totalMilliVolts / samples) / 1000.0;
}


// ============================================================
// FUNCTION: CONNECT TO WIFI
// ============================================================

void startWiFiConnection()
{
  if (WiFi.status() == WL_CONNECTED || wifiAttemptInProgress) return;

  Serial.println();
  Serial.println("Starting Wi-Fi connection attempt...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  wifiAttemptStarted = millis();
  wifiAttemptInProgress = true;
}

void maintainWiFi()
{
  if (WiFi.status() == WL_CONNECTED)
  {
    if (wifiAttemptInProgress)
    {
      Serial.println("Wi-Fi connected.");
      Serial.print("IP address: ");
      Serial.println(WiFi.localIP());
      Serial.print("RSSI: ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");
    }
    wifiAttemptInProgress = false;
    return;
  }

  if (wifiAttemptInProgress && millis() - wifiAttemptStarted >= WIFI_CONNECT_TIMEOUT)
  {
    Serial.println("Wi-Fi connection timed out; scheduling retry.");
    WiFi.disconnect(false, false);
    wifiAttemptInProgress = false;
    nextWiFiAttempt = millis() + WIFI_RETRY_INTERVAL;
  }

  if (!wifiAttemptInProgress && (long)(millis() - nextWiFiAttempt) >= 0)
  {
    startWiFiConnection();
  }
}

// ============================================================
// FUNCTION: READ SENSORS
// ============================================================

void readSensors(
  float &temperatureC,
  bool  &tempValid,
  float &tdsADC,
  float &tdsVoltage,
  float &tdsPPM,
  float &turbidityADC,
  float &turbidityVoltage,
  float &turbidityEstimate
)
{
  // ----------------------------------------------------------
  // TDS RAW ADC & VOLTAGE
  // ----------------------------------------------------------

  tdsADC = readAverageADC(TDS_PIN);
  tdsVoltage = readAverageVoltage(TDS_PIN);


  // ----------------------------------------------------------
  // TEMPERATURE & VALIDITY CHECK
  // ----------------------------------------------------------

  temperatureSensor.requestTemperatures();

  float rawTempC =
    temperatureSensor.getTempCByIndex(0);

  // DS18B20 Disconnection & Fault Detection:
  // - DEVICE_DISCONNECTED_C (-127.0°C) is returned if probe/bus is disconnected or pull-up is missing.
  // - 85.0°C is the DS18B20 power-on reset state if read before first conversion completes.
  // - Physically plausible freshwater aquatic temperatures range from -5.0°C to 50.0°C.
  // - Detect any disconnection, NaN, or out-of-range reading.
  if (rawTempC == DEVICE_DISCONNECTED_C ||
      rawTempC <= -100.0 ||
      rawTempC < -5.0 ||
      rawTempC >= 85.0 ||
      isnan(rawTempC))
  {
    tempValid = false;
    temperatureC = rawTempC; // Retain raw reading for diagnostic reporting
  }
  else
  {
    tempValid = true;
    temperatureC = rawTempC;
  }


  // ----------------------------------------------------------
  // TDS TEMPERATURE COMPENSATION
  //
  // Standard equation: compensationCoefficient = 1.0 + 0.02 * (T - 25.0)
  //
  // SAFETY CORRECTION:
  // If temperature is invalid (e.g. -127°C disconnected), using it directly
  // yields: 1.0 + 0.02 * (-127.0 - 25.0) = -2.04 (negative coefficient).
  // This inverts the voltage, corrupts the polynomial estimation, and
  // silently clamps TDS to 0 ppm.
  //
  // When temperature is invalid, safely fallback to standard reference
  // temperature (25.0°C), making compensationCoefficient = 1.0 (uncompensated).
  // ----------------------------------------------------------

  float compTemp = tempValid ? temperatureC : 25.0;

  float compensationCoefficient =
    1.0 + 0.02 * (compTemp - 25.0);

  float compensatedVoltage =
    tdsVoltage / compensationCoefficient;


  // ----------------------------------------------------------
  // TDS ESTIMATION
  //
  // Based on the current TDS model.
  // NOT absolute calibration.
  // ----------------------------------------------------------

  tdsPPM =
    (133.42 * compensatedVoltage * compensatedVoltage * compensatedVoltage
    - 255.86 * compensatedVoltage * compensatedVoltage
    + 857.39 * compensatedVoltage)
    * 0.5;

  tdsPPM =
    tdsPPM * TDS_CALIBRATION_FACTOR
    + TDS_OFFSET;


  // Prevent negative values

  if (tdsPPM < 0)
  {
    tdsPPM = 0;
  }


  // ----------------------------------------------------------
  // TURBIDITY
  //
  // HARDWARE COMPATIBILITY & VOLTAGE LIMITS:
  // Commercial optical turbidity modules (e.g. Gravity / DFRobot) powered
  // at 5V output up to 4.5V in clear water. ESP32 ADC pins tolerate max 3.6V.
  // If sensor outputs > 3.3V, an external resistive divider or level shifter
  // is required on GPIO 35. This firmware reads the pin directly and does NOT
  // assume a divider is installed.
  //
  // VOLTAGE DIRECTION & CALIBRATION NOTICE:
  // Commercial optical turbidity sensors output high voltage in clear water
  // and voltage decreases as turbidity increases (inverse relationship).
  // The current prototype estimate uses direct baseline subtraction:
  //   turbidityEstimate = (V - V_baseline) * 1000 * Factor.
  // Physical calibration with Formazin NTU standards is required before
  // scientific deployment. The existing formula is preserved without inventing constants.
  // ----------------------------------------------------------

  turbidityADC = readAverageADC(TURBIDITY_PIN);
  turbidityVoltage = readAverageVoltage(TURBIDITY_PIN);


  // Remove baseline

  float correctedTurbidityVoltage =
    turbidityVoltage - TURBIDITY_BASELINE_VOLTAGE;

  if (correctedTurbidityVoltage < 0)
  {
    correctedTurbidityVoltage = 0;
  }


  // Current prototype estimate

  turbidityEstimate =
    correctedTurbidityVoltage
    * 1000.0
    * TURBIDITY_CALIBRATION_FACTOR;


  if (turbidityEstimate < 0)
  {
    turbidityEstimate = 0;
  }
}


// ============================================================
// FUNCTION: SEND DATA TO FIREBASE
// ============================================================

bool sendToFirebase(
  float temperatureC,
  bool  tempValid,
  float tdsADC,
  float tdsVoltage,
  float tdsPPM,
  float turbidityADC,
  float turbidityVoltage,
  float turbidityEstimate
)
{
  if (WiFi.status() != WL_CONNECTED)
  {
    Serial.println("Firebase: Wi-Fi not connected.");
    return false;
  }


  // ----------------------------------------------------------
  // Create JSON payload
  // ----------------------------------------------------------

  String json = "{";

  // Temperature & explicit validity indicator
  if (tempValid)
  {
    json += "\"temperature\":";
    json += String(temperatureC, 2);
  }
  else
  {
    json += "\"temperature\":null";
  }

  json += ",";
  json += "\"tempValid\":";
  json += (tempValid ? "true" : "false");

  json += ",";
  json += "\"temp_valid\":";
  json += (tempValid ? "true" : "false");

  json += ",";
  json += "\"temperatureStatus\":\"";
  json += (tempValid ? "valid" : "disconnected_or_invalid");
  json += "\"";

  json += ",";

  json += "\"tds\":";
  json += String(tdsPPM, 2);

  json += ",";

  json += "\"tdsADC\":";
  json += String(tdsADC, 0);

  json += ",";

  json += "\"tdsVoltage\":";
  json += String(tdsVoltage, 3);

  json += ",";

  json += "\"turbidity\":";
  json += String(turbidityEstimate, 2);

  json += ",";

  json += "\"turbidityADC\":";
  json += String(turbidityADC, 0);

  json += ",";

  json += "\"turbidityVoltage\":";
  json += String(turbidityVoltage, 3);

  // ----------------------------------------------------------
  // pH currently unavailable
  // ----------------------------------------------------------

  json += ",";
  json += "\"ph\":null";


  // ----------------------------------------------------------
  // Dissolved Oxygen currently unavailable
  // ----------------------------------------------------------

  json += ",";
  json += "\"dissolvedOxygen\":null";


  // ----------------------------------------------------------
  // Device information
  // ----------------------------------------------------------

  json += ",";
  json += "\"wifiRSSI\":";
  json += String(WiFi.RSSI());

  json += ",";
  json += "\"uptimeMs\":";
  json += String(millis());


  // ----------------------------------------------------------
  // Sensor status
  // ----------------------------------------------------------

  json += ",";
  if (tempValid)
  {
    json += "\"tdsStatus\":\"estimated\"";
  }
  else
  {
    json += "\"tdsStatus\":\"estimated_temp_fallback\"";
  }

  json += ",";
  json += "\"turbidityStatus\":\"prototype_estimate\"";

  json += ",";
  json += "\"phStatus\":\"sensor_not_installed\"";

  json += ",";
  json += "\"doStatus\":\"sensor_not_installed\"";


  json += "}";


  // ----------------------------------------------------------
  // HTTP CLIENT
  // ----------------------------------------------------------

  HTTPClient http;


  // ==========================================================
  // 1. UPDATE LATEST READING
  // ==========================================================

  String latestURL =
    String(FIREBASE_HOST) +
    "/sensorData/latest.json";


  Serial.println();
  Serial.println("Sending latest data to Firebase...");
  Serial.println("URL:");
  Serial.println(latestURL);


  http.begin(latestURL);

  http.addHeader(
    "Content-Type",
    "application/json"
  );


  int httpCode =
    http.PUT(json);


  Serial.print("Firebase latest HTTP code: ");
  Serial.println(httpCode);


  if (httpCode > 0)
  {
    String response =
      http.getString();

    Serial.print("Firebase response: ");
    Serial.println(response);
  }
  else
  {
    Serial.print("Firebase HTTP error: ");
    Serial.println(http.errorToString(httpCode));
  }


  http.end();


  // ==========================================================
  // 2. ADD READING TO HISTORY
  // ==========================================================

  String historyURL =
    String(FIREBASE_HOST) +
    "/sensorData/history.json";


  Serial.println();
  Serial.println("Saving reading to history...");


  http.begin(historyURL);

  http.addHeader(
    "Content-Type",
    "application/json"
  );


  int historyCode =
    http.POST(json);


  Serial.print("Firebase history HTTP code: ");
  Serial.println(historyCode);


  if (historyCode > 0)
  {
    String response =
      http.getString();

    Serial.print("History response: ");
    Serial.println(response);
  }
  else
  {
    Serial.print("Firebase history error: ");
    Serial.println(
      http.errorToString(historyCode)
    );
  }


  http.end();


  bool latestSuccess = (httpCode >= 200 && httpCode < 300);
  bool historySuccess = (historyCode >= 200 && historyCode < 300);

  Serial.print("Latest upload: ");
  Serial.println(latestSuccess ? "SUCCESS" : "FAILED");
  Serial.print("History upload: ");
  Serial.println(historySuccess ? "SUCCESS" : "FAILED");

  return latestSuccess && historySuccess;
}


// ============================================================
// SETUP
// ============================================================

void setup()
{
  Serial.begin(115200);

  delay(1000);


  // ----------------------------------------------------------
  // ADC
  // ----------------------------------------------------------

  // Configure 12-bit ADC resolution (0–4095 counts)
  analogReadResolution(12);

  // Set 11dB attenuation: full-scale voltage range ~3.3V
  // WARNING: GPIO 34 & 35 are limited to 3.6V max input. External conditioning
  // is required if connected sensor produces > 3.3V.
  analogSetAttenuation(ADC_11db);


  // ----------------------------------------------------------
  // Temperature sensor
  // ----------------------------------------------------------

  temperatureSensor.begin();


  // ----------------------------------------------------------
  // Header
  // ----------------------------------------------------------

  Serial.println();
  Serial.println("================================================");
  Serial.println("        AI-BASED AQUATIC HABITAT");
  Serial.println("        SENSOR NODE - IOT SYSTEM");
  Serial.println("================================================");

  Serial.println();

  Serial.println("Sensors:");
  Serial.println("  TDS         -> GPIO 34");
  Serial.println("  Turbidity   -> GPIO 35");
  Serial.println("  Temperature -> GPIO 4");

  Serial.println();

  Serial.println("Cloud:");
  Serial.println("  Firebase Realtime Database");

  Serial.println();

  Serial.println("TDS Calibration Factor      : ");
  Serial.println(TDS_CALIBRATION_FACTOR, 4);

  Serial.println("TDS Offset                  : ");
  Serial.print(TDS_OFFSET, 2);
  Serial.println(" ppm");

  Serial.println();

  Serial.println("Turbidity Baseline Voltage  : ");
  Serial.print(TURBIDITY_BASELINE_VOLTAGE, 3);
  Serial.println(" V");

  Serial.println("Turbidity Calibration Factor: ");
  Serial.println(TURBIDITY_CALIBRATION_FACTOR, 4);

  Serial.println();

  Serial.println("pH Sensor                   : NOT INSTALLED");
  Serial.println("DO Sensor                   : NOT INSTALLED");

  Serial.println();

  Serial.println("WARNING:");
  Serial.println("TDS is MODEL-ESTIMATED.");
  Serial.println("Turbidity is a PROTOTYPE ESTIMATE.");
  Serial.println("pH and DO are currently unavailable.");

  Serial.println("================================================");


  // ----------------------------------------------------------
  // Wi-Fi
  // ----------------------------------------------------------

  startWiFiConnection();
}


// ============================================================
// LOOP
// ============================================================

void loop()
{
  // ----------------------------------------------------------
  // Maintain Wi-Fi
  // ----------------------------------------------------------

  maintainWiFi();


  // ----------------------------------------------------------
  // Read every 10 seconds
  // ----------------------------------------------------------

  if (
    millis() - lastSensorRead >= SENSOR_INTERVAL
    ||
    lastSensorRead == 0
  )
  {
    lastSensorRead = millis();


    // --------------------------------------------------------
    // Variables
    // --------------------------------------------------------

    float temperatureC;
    bool  tempValid;

    float tdsADC;
    float tdsVoltage;
    float tdsPPM;

    float turbidityADC;
    float turbidityVoltage;
    float turbidityEstimate;


    // --------------------------------------------------------
    // Read sensors
    // --------------------------------------------------------

    readSensors(
      temperatureC,
      tempValid,
      tdsADC,
      tdsVoltage,
      tdsPPM,
      turbidityADC,
      turbidityVoltage,
      turbidityEstimate
    );


    // --------------------------------------------------------
    // SERIAL MONITOR
    // --------------------------------------------------------

    Serial.println();
    Serial.println("------------- SENSOR DATA -------------");

    if (tempValid)
    {
      Serial.print("Temperature | ");
      Serial.print(temperatureC, 2);
      Serial.println(" °C");
    }
    else
    {
      Serial.print("Temperature | INVALID / DISCONNECTED (code: ");
      Serial.print(temperatureC, 2);
      Serial.println(" °C) - Using 25.0°C fallback for TDS");
    }


    Serial.print("TDS         | ADC: ");
    Serial.print(tdsADC, 0);

    Serial.print(" | Voltage: ");
    Serial.print(tdsVoltage, 3);

    Serial.print(" V | Estimated TDS: ");
    Serial.print(tdsPPM, 1);

    if (tempValid)
    {
      Serial.println(" ppm");
    }
    else
    {
      Serial.println(" ppm (uncompensated, 25°C ref)");
    }


    Serial.print("Turbidity   | ADC: ");
    Serial.print(turbidityADC, 0);

    Serial.print(" | Voltage: ");
    Serial.print(turbidityVoltage, 3);

    Serial.print(" V | Prototype Estimate: ");
    Serial.print(turbidityEstimate, 2);

    Serial.println();


    Serial.println("---------------------------------------");

    Serial.println("pH          | NOT AVAILABLE");

    Serial.println("DO          | NOT AVAILABLE");

    Serial.println("---------------------------------------");


    // --------------------------------------------------------
    // FIREBASE
    // --------------------------------------------------------

    bool firebaseSuccess =
      sendToFirebase(
        temperatureC,
        tempValid,
        tdsADC,
        tdsVoltage,
        tdsPPM,
        turbidityADC,
        turbidityVoltage,
        turbidityEstimate
      );


    if (firebaseSuccess)
    {
      Serial.println();
      Serial.println(">>> Firebase upload successful.");
    }
    else
    {
      Serial.println();
      Serial.println(">>> Firebase upload failed.");
    }


    Serial.println("=======================================");
  }
}