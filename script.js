/* =========================================================
   AI-BASED AQUATIC HABITAT ASSESSMENT
   Dashboard JavaScript
   ========================================================= */


/* =========================================================
   1. CONFIGURATION
   ========================================================= */

// Determine backend API origin:
// If page is served on port 5000 (direct Flask), use same origin.
// If page is served on port 5500 (dev server), target Flask on port 5000.
const API_BASE_URL = (typeof window !== "undefined" && window.location.port === "5000")
    ? ""
    : "http://127.0.0.1:5000";

const LATEST_URL = `${API_BASE_URL}/api/latest`;

const HISTORY_URL = `${API_BASE_URL}/api/history`;

const SIMULATE_URL = `${API_BASE_URL}/api/simulate`;

const STALE_TIME = 60 * 1000;

console.log("[Dashboard Config] API_BASE_URL:", API_BASE_URL || "(same origin)");

/* =========================================================
   2. CHART REFERENCES
   ========================================================= */

let temperatureChart = null;
let turbidityChart = null;
let tdsChart = null;
let scoreChart = null;


/* =========================================================
   3. ELEMENT REFERENCES
   ========================================================= */

const temperatureElement =
    document.getElementById("temperature");

const turbidityElement =
    document.getElementById("turbidity");

const tdsElement =
    document.getElementById("tds");

const scoreElement =
    document.getElementById("score");

const conditionElement =
    document.getElementById("condition");

const lastUpdatedElement =
    document.getElementById("lastUpdated");

const problemsElement =
    document.getElementById("problems");

const recommendationsElement =
    document.getElementById("recommendations");

const connectionStatusElement =
    document.getElementById("connectionStatus");

const temperatureStatusElement =
    document.getElementById("temperatureStatus");

const tdsStatusElement =
    document.getElementById("tdsStatus");

const turbidityStatusElement =
    document.getElementById("turbidityStatus");

const phStatusElement =
    document.getElementById("phStatus");

const doStatusElement =
    document.getElementById("doStatus");

const deviceIdElement =
    document.getElementById("deviceId");

const wifiRSSElement =
    document.getElementById("wifiRSSI");

const uptimeElement =
    document.getElementById("uptime");

const historyStatusElement =
    document.getElementById("historyStatus");

const predictedPhElement =
    document.getElementById("predictedPh");

const predictedDoElement =
    document.getElementById("predictedDo");

const mlStatusElement =
    document.getElementById("mlStatus");


/* =========================================================
   4. STATE
   ========================================================= */

let lastKnownData = null;
let lastUptimeMs = null;
let lastUptimeReceiveTime = null;


/* =========================================================
   5. FORMAT UPTIME
   ========================================================= */

function formatUptime(milliseconds) {

    if (!milliseconds || milliseconds < 0) {
        return "--";
    }

    const totalSeconds =
        Math.floor(milliseconds / 1000);

    const days =
        Math.floor(totalSeconds / 86400);

    const hours =
        Math.floor((totalSeconds % 86400) / 3600);

    const minutes =
        Math.floor((totalSeconds % 3600) / 60);

    const seconds =
        totalSeconds % 60;


    if (days > 0) {
        return `${days}d ${hours}h ${minutes}m`;
    }

    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }

    if (minutes > 0) {
        return `${minutes}m ${seconds}s`;
    }

    return `${seconds}s`;
}


/* =========================================================
   6. FORMAT DATE
   ========================================================= */

function formatTimestamp(timestamp) {
    if (!timestamp || timestamp < 1577836800000) {
        return "Timestamp unavailable";
    }

    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
        return "Timestamp unavailable";
    }

    const options = {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
    };
    return date.toLocaleString('default', options).replace(/,/g, '');
}


/* =========================================================
   7. WATER QUALITY ANALYSIS (FRONTEND FALLBACK)
   ========================================================= */

/**
 * This is the original frontend-only rule-based assessment.
 * It is now used ONLY for historical chart scores, since
 * the backend provides the authoritative live assessment.
 */

function analyzeWaterQuality(
    temperature,
    turbidity,
    tds
) {

    let score = 100;

    const problems = [];

    const recommendations = [];


    /* Temperature */

    if (
        temperature < 20 ||
        temperature > 32
    ) {

        score -= 20;

        problems.push(
            `Temperature is outside the preferred range (${temperature.toFixed(1)} °C).`
        );

        recommendations.push(
            "Monitor water temperature and investigate sources of excessive heating or cooling."
        );
    }


    /* Turbidity */

    if (turbidity > 25) {

        score -= 30;

        problems.push(
            `High turbidity detected (${turbidity.toFixed(1)} NTU*).`
        );

        recommendations.push(
            "Reduce sediment and soil runoff entering the water body."
        );

    } else if (turbidity > 10) {

        score -= 15;

        problems.push(
            `Moderate turbidity detected (${turbidity.toFixed(1)} NTU*).`
        );

        recommendations.push(
            "Monitor sediment and runoff entering the water body."
        );
    }


    /* TDS */

    if (tds > 500) {

        score -= 30;

        problems.push(
            `High TDS detected (${tds.toFixed(1)} ppm*).`
        );

        recommendations.push(
            "Investigate possible sources of dissolved salts and contaminants."
        );

    } else if (tds > 300) {

        score -= 10;

        problems.push(
            `Elevated TDS detected (${tds.toFixed(1)} ppm*).`
        );

        recommendations.push(
            "Monitor dissolved solids and investigate possible pollution sources."
        );
    }


    score =
        Math.max(
            0,
            Math.min(100, score)
        );


    let condition;


    if (score >= 80) {

        condition = "Excellent";

    } else if (score >= 60) {

        condition = "Good";

    } else if (score >= 40) {

        condition = "Moderate";

    } else {

        condition = "Poor";
    }


    return {
        score,
        condition,
        problems,
        recommendations
    };
}


/* =========================================================
   8. UPDATE SCORE VISUAL
   ========================================================= */

function updateScoreVisual(score, condition) {

    scoreElement.textContent =
        `${score}%`;

    conditionElement.textContent =
        condition;


    if (score < 40) {

        scoreElement.style.borderColor =
            "var(--poor)";

        conditionElement.style.color =
            "var(--poor)";

    } else if (score < 60) {

        scoreElement.style.borderColor =
            "var(--moderate)";

        conditionElement.style.color =
            "var(--moderate)";

    } else if (score < 80) {

        scoreElement.style.borderColor =
            "var(--good)";

        conditionElement.style.color =
            "var(--good)";

    } else {

        scoreElement.style.borderColor =
            "var(--excellent)";

        conditionElement.style.color =
            "var(--excellent)";
    }
}


/* =========================================================
   9. DISPLAY PROBLEMS
   ========================================================= */

function displayProblems(problems) {

    problemsElement.innerHTML = "";


    if (!problems || problems.length === 0) {

        const item =
            document.createElement("li");

        item.textContent =
            "✓ All currently monitored parameters are within the configured ranges.";

        item.style.borderLeftColor =
            "var(--good)";

        item.style.background =
            "#f0fdf4";

        problemsElement.appendChild(item);

        return;
    }


    problems.forEach(problem => {

        const item =
            document.createElement("li");

        item.textContent =
            `⚠ ${problem}`;

        problemsElement.appendChild(item);
    });
}


/* =========================================================
   10. DISPLAY RECOMMENDATIONS
   ========================================================= */

function displayRecommendations(
    recommendations
) {

    recommendationsElement.innerHTML = "";


    if (!recommendations || recommendations.length === 0) {

        const item =
            document.createElement("li");

        item.textContent =
            "✓ No restoration action is currently indicated by the monitored parameters.";

        recommendationsElement.appendChild(item);

        return;
    }


    recommendations.forEach(recommendation => {

        const item =
            document.createElement("li");

        item.textContent =
            `→ ${recommendation}`;

        recommendationsElement.appendChild(item);
    });
}


/* =========================================================
   11. SENSOR STATUS
   ========================================================= */

function updateSensorStatus(sensorData, mlData) {

    // Temperature
    if (sensorData.temperature !== undefined && sensorData.temperature !== null) {
        temperatureStatusElement.textContent =
            "Available • Measured";
        temperatureStatusElement.style.color =
            "var(--good)";
    } else {
        temperatureStatusElement.textContent = "Unavailable";
        temperatureStatusElement.style.color = "var(--poor)";
    }

    // TDS
    if (sensorData.tds !== undefined && sensorData.tds !== null) {
        tdsStatusElement.textContent =
            "Available • Prototype estimate";
        tdsStatusElement.style.color =
            "var(--good)";
    } else {
        tdsStatusElement.textContent = "Unavailable";
        tdsStatusElement.style.color = "var(--poor)";
    }

    // Turbidity
    if (sensorData.turbidity !== undefined && sensorData.turbidity !== null) {
        turbidityStatusElement.textContent =
            "Available • Prototype estimate";
        turbidityStatusElement.style.color =
            "var(--good)";
    } else {
        turbidityStatusElement.textContent = "Unavailable";
        turbidityStatusElement.style.color = "var(--poor)";
    }

    // pH and DO (ML predicted)
    if (mlData && mlData.available) {
        phStatusElement.textContent = "ML prediction available";
        phStatusElement.style.color = "var(--good)";

        doStatusElement.textContent = "ML prediction available";
        doStatusElement.style.color = "var(--good)";
    } else {
        phStatusElement.textContent = "ML prediction unavailable";
        phStatusElement.style.color = "var(--text-muted)";

        doStatusElement.textContent = "ML prediction unavailable";
        doStatusElement.style.color = "var(--text-muted)";
    }
}


/* =========================================================
   12. DEVICE INFORMATION
   ========================================================= */

function updateDeviceInformation(data) {

    deviceIdElement.textContent =
        data.device || data.device_id || "NODE-01";


    const rawData = data.raw_data || data;

    wifiRSSElement.textContent =
        rawData.wifiRSSI !== undefined
            ? rawData.wifiRSSI
            : "--";


    uptimeElement.textContent =
        rawData.uptimeMs !== undefined
            ? formatUptime(rawData.uptimeMs)
            : "--";
}


/* =========================================================
   13. UPDATE DASHBOARD
   ========================================================= */

function updateDashboard(data) {

    const sensorData = data.sensor_data || data;
    const mlData = data.ml_prediction || {};
    const assessment = data.assessment || {};

    const temperature =
        Number(sensorData.temperature);

    const turbidity =
        Number(sensorData.turbidity);

    const tds =
        Number(sensorData.tds);


    // Update sensor value displays
    if (Number.isFinite(temperature)) {
        temperatureElement.textContent =
            temperature.toFixed(1);
    } else {
        temperatureElement.textContent = "--";
    }

    if (Number.isFinite(turbidity)) {
        turbidityElement.textContent =
            turbidity.toFixed(1);
    } else {
        turbidityElement.textContent = "--";
    }

    if (Number.isFinite(tds)) {
        tdsElement.textContent =
            tds.toFixed(1);
    } else {
        tdsElement.textContent = "--";
    }


    // --- Assessment (from backend) ---
    if (assessment.hss !== null && assessment.hss !== undefined) {

        updateScoreVisual(assessment.hss, assessment.category);
        displayProblems(assessment.problems);
        displayRecommendations(assessment.recommendations);

    } else if (
        Number.isFinite(temperature) &&
        Number.isFinite(turbidity) &&
        Number.isFinite(tds)
    ) {
        // Backend didn't provide assessment, but we have sensor data
        // Fall back to frontend-only rule-based assessment
        const analysis = analyzeWaterQuality(temperature, turbidity, tds);
        updateScoreVisual(analysis.score, analysis.condition);
        displayProblems(analysis.problems);
        displayRecommendations(analysis.recommendations);

    } else {

        scoreElement.textContent =
            "N/A";

        conditionElement.textContent =
            "Score unavailable";

        conditionElement.style.color =
            "var(--text-muted)";

        scoreElement.style.borderColor =
            "var(--border)";

        problemsElement.innerHTML = "<li>Waiting for sensor data...</li>";
        recommendationsElement.innerHTML = "<li>Recommendations will appear after analysis.</li>";
    }


    // --- ML Predictions ---
    if (mlData.available) {
        predictedPhElement.textContent = mlData.ph !== null ? mlData.ph.toFixed(2) : "--";
        predictedDoElement.textContent = mlData.do !== null ? mlData.do.toFixed(2) : "--";

        const phPred = document.getElementById("phPredictStatus");
        if (phPred) phPred.textContent = "ML predicted (via TDS→conductance conversion)";
        const doPred = document.getElementById("doPredictStatus");
        if (doPred) doPred.textContent = "ML predicted (via TDS→conductance conversion)";

        mlStatusElement.textContent = "Status: " + mlData.status;
        mlStatusElement.style.color = "var(--good)";
        mlStatusElement.style.background = "#f0fdf4";
    } else {
        predictedPhElement.textContent = "--";
        predictedDoElement.textContent = "--";

        const phPred = document.getElementById("phPredictStatus");
        if (phPred) phPred.textContent = "ML prediction unavailable";
        const doPred = document.getElementById("doPredictStatus");
        if (doPred) doPred.textContent = "ML prediction unavailable";

        mlStatusElement.textContent = "Status: " + (mlData.status || data.message || "Waiting for valid inputs");
        mlStatusElement.style.color = "var(--moderate)";
        mlStatusElement.style.background = "#fffbeb";
    }


    // --- Sensor availability ---
    updateSensorStatus(sensorData, mlData);

    // --- Device info ---
    updateDeviceInformation(data);

    // --- Stale detection ---
    if (data.is_stale) {
        connectionStatusElement.textContent = "● Device offline / Data stale";
        connectionStatusElement.style.color = "var(--poor)";
        document.body.classList.add("stale");
    }

    // --- Store for simulator ---
    lastKnownData = data;

    // Update simulator live side
    updateSimulatorLiveValues(data);
}


/* =========================================================
   14. CONNECTION STATUS
   ========================================================= */

function updateConnectionStatus(timestamp, uptimeMs) {
    const receivedTime = Date.now();
    let isStale = false;

    if (timestamp && timestamp > 1577836800000) {
        if (receivedTime - timestamp > STALE_TIME) isStale = true;
    } else if (uptimeMs !== undefined && uptimeMs !== null) {
        if (lastUptimeMs === uptimeMs) {
            if (receivedTime - lastUptimeReceiveTime > STALE_TIME) isStale = true;
        } else {
            lastUptimeMs = uptimeMs;
            lastUptimeReceiveTime = receivedTime;
        }
    } else {
        isStale = false;
    }

    if (!isStale) {
        connectionStatusElement.textContent = "● Device connected";
        connectionStatusElement.style.color = "var(--good)";
        document.body.classList.remove("stale");
    } else {
        connectionStatusElement.textContent = "● Device offline / Data stale";
        connectionStatusElement.style.color = "var(--poor)";
        document.body.classList.add("stale");
    }
}


/* =========================================================
   15. LOAD LATEST DATA
   ========================================================= */

async function loadLatestData() {

    try {

        console.log(`[Dashboard Fetch] GET ${LATEST_URL}`);

        const response =
            await fetch(LATEST_URL);


        if (!response.ok) {
            let errorMsg = `API returned HTTP ${response.status}`;
            if (response.status === 502) {
                errorMsg = "Firebase database unavailable (HTTP 502)";
            } else if (response.status === 404) {
                errorMsg = "No sensor data in Firebase (HTTP 404)";
            }
            throw new Error(errorMsg);
        }


        let data;
        try {
            data = await response.json();
        } catch (jsonErr) {
            console.error("[Dashboard JSON Parse Error]", jsonErr);
            throw new Error("Invalid JSON response from Flask backend");
        }

        if (!data || !data.success) {
            throw new Error(
                data ? (data.error || "Backend returned unsuccessful status") : "No data returned"
            );
        }


        console.log(
            "[Dashboard] Latest API data received successfully:",
            data
        );


        updateDashboard(data);


        const dataTimestamp = data.timestamp;

        if (dataTimestamp && dataTimestamp > 1577836800000) {
            lastUpdatedElement.textContent = "Last updated: " + formatTimestamp(dataTimestamp);
        } else {
            // Use server time
            if (data.server_time) {
                const serverDate = new Date(data.server_time);
                lastUpdatedElement.textContent = "Last updated: " + serverDate.toLocaleString();
            } else {
                lastUpdatedElement.textContent = "Last updated: " + new Date().toLocaleString();
            }
        }

        const rawData = data.raw_data || data;
        updateConnectionStatus(data.timestamp, rawData.uptimeMs);

    }
    catch (error) {

        console.error(
            "[Dashboard Latest Data Error]",
            error
        );

        document.body.classList.add("stale");
        scoreElement.textContent = "N/A";
        scoreElement.style.borderColor = "var(--border)";
        conditionElement.textContent = "Assessment Unavailable";
        conditionElement.style.color = "var(--poor)";

        if (error.name === "TypeError" || (error.message && (error.message.includes("fetch") || error.message.includes("Network")))) {
            connectionStatusElement.textContent =
                "● Backend unavailable";
            connectionStatusElement.style.color =
                "var(--poor)";
            problemsElement.innerHTML =
                `<li>⚠ Flask backend unavailable or CORS blocked. Verify backend is running at ${API_BASE_URL || "http://127.0.0.1:5000"}</li>`;
            recommendationsElement.innerHTML =
                "<li>→ Start backend with: python backend/app.py</li>";
        } else if (error.message && error.message.includes("502")) {
            connectionStatusElement.textContent =
                "● Firebase unavailable";
            connectionStatusElement.style.color =
                "var(--poor)";
            problemsElement.innerHTML =
                "<li>⚠ Firebase Realtime Database is unreachable from Flask backend.</li>";
            recommendationsElement.innerHTML =
                "<li>→ Check Internet connectivity and Firebase RTDB status.</li>";
        } else if (error.message && error.message.includes("404")) {
            connectionStatusElement.textContent =
                "● No sensor data";
            connectionStatusElement.style.color =
                "var(--poor)";
            problemsElement.innerHTML =
                "<li>⚠ No sensor reading records found in Firebase Realtime Database.</li>";
            recommendationsElement.innerHTML =
                "<li>→ Ensure ESP32 node has powered on and uploaded initial readings.</li>";
        } else {
            connectionStatusElement.textContent =
                "● Offline / No data";
            connectionStatusElement.style.color =
                "var(--poor)";
            problemsElement.innerHTML =
                `<li>⚠ ${error.message}</li>`;
            recommendationsElement.innerHTML =
                "<li>→ Check backend or Firebase connection logs.</li>";
        }
    }
}


/* =========================================================
   16. PREPARE HISTORY DATA
   ========================================================= */

const FIREBASE_PUSH_CHARS = "-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz";

function extractRecordTimestamp(record) {
    if (record.timestamp && Number(record.timestamp) > 1577836800000) {
        return Number(record.timestamp);
    }
    if (record.time && Number(record.time) > 1577836800000) {
        return Number(record.time);
    }
    // Attempt decoding Firebase push ID (first 8 characters encode 72-bit epoch timestamp)
    if (record.key && typeof record.key === "string" && record.key.length >= 8) {
        let time = 0;
        let valid = true;
        for (let i = 0; i < 8; i++) {
            const val = FIREBASE_PUSH_CHARS.indexOf(record.key.charAt(i));
            if (val === -1) {
                valid = false;
                break;
            }
            time = (time * 64) + val;
        }
        if (valid && time > 1577836800000) {
            return time;
        }
    }
    return null;
}

function prepareHistoryData(history) {

    if (!history) {
        return [];
    }

    const records =
        Object.entries(history).map(
            ([key, value]) => {
                return {
                    key,
                    ...value
                };
            }
        );

    // Sort chronologically:
    // 1. By true timestamp (explicit or decoded from Firebase push ID)
    // 2. By Firebase push ID key (naturally lexicographically chronological)
    // 3. Fallback to uptimeMs only if keys are identical or missing
    records.sort(
        (a, b) => {
            const timeA = extractRecordTimestamp(a);
            const timeB = extractRecordTimestamp(b);

            if (timeA !== null && timeB !== null) {
                return timeA - timeB;
            }

            if (a.key && b.key && a.key !== b.key) {
                return a.key < b.key ? -1 : 1;
            }

            return Number(a.uptimeMs || 0) - Number(b.uptimeMs || 0);
        }
    );

    return records;
}


/* =========================================================
   17. GET RECORD TIME
   ========================================================= */

function getRecordTime(record, index) {

    const ts = extractRecordTimestamp(record);

    if (ts !== null) {
        const date = new Date(ts);
        if (!isNaN(date.getTime())) {
            return date.toLocaleTimeString(
                [],
                {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit"
                }
            );
        }
    }

    /*
       Fallback to reading index if no timestamp is extractable.
    */
    return `Reading ${index + 1}`;
}


/* =========================================================
   18. CREATE CHART OPTIONS
   ========================================================= */

function getChartOptions(yTitle) {

    return {

        responsive: true,

        maintainAspectRatio: false,

        interaction: {
            mode: "index",
            intersect: false
        },

        plugins: {

            legend: {
                display: false
            },

            tooltip: {
                enabled: true
            }
        },

        scales: {

            x: {

                title: {
                    display: true,
                    text: "Reading"
                },

                grid: {
                    display: false
                }
            },

            y: {

                title: {
                    display: true,
                    text: yTitle
                },

                beginAtZero: false
            }
        },

        elements: {

            point: {
                radius: 2,
                hoverRadius: 5
            },

            line: {
                tension: 0.25
            }
        }
    };
}


/* =========================================================
   19. CREATE HISTORY CHARTS
   ========================================================= */

function createHistoryCharts(records) {

    if (!records || records.length === 0) {

        historyStatusElement.textContent =
            "No historical readings available.";

        return;
    }


    const labels =
        records.map(
            (record, index) =>
                getRecordTime(record, index)
        );


    const temperatures =
        records.map(
            record =>
                Number(record.temperature)
        );


    const turbidities =
        records.map(
            record =>
                Number(record.turbidity)
        );


    const tdsValues =
        records.map(
            record =>
                Number(record.tds)
        );


    /*
       Calculate score for every historical reading.
       Uses frontend-only rule-based scoring for consistency.
    */

    const scores =
        records.map(record => {

            const temperature =
                Number(record.temperature);

            const turbidity =
                Number(record.turbidity);

            const tds =
                Number(record.tds);


            if (
                !Number.isFinite(temperature) ||
                !Number.isFinite(turbidity) ||
                !Number.isFinite(tds)
            ) {

                return null;
            }


            return analyzeWaterQuality(
                temperature,
                turbidity,
                tds
            ).score;
        });


    /*
       Destroy old charts before creating new ones.
       This prevents duplicate charts when Firebase
       history is refreshed.
    */

    if (temperatureChart) {
        temperatureChart.destroy();
    }

    if (turbidityChart) {
        turbidityChart.destroy();
    }

    if (tdsChart) {
        tdsChart.destroy();
    }

    if (scoreChart) {
        scoreChart.destroy();
    }


    /* -----------------------------------------
       Temperature Chart
       ----------------------------------------- */

    temperatureChart =
        new Chart(
            document.getElementById(
                "temperatureChart"
            ),
            {

                type: "line",

                data: {

                    labels,

                    datasets: [{

                        label: "Temperature",

                        data: temperatures,

                        borderWidth: 2,

                        fill: false,

                        tension: 0.25
                    }]
                },

                options:
                    getChartOptions(
                        "Temperature (°C)"
                    )
            }
        );


    /* -----------------------------------------
       Turbidity Chart
       ----------------------------------------- */

    turbidityChart =
        new Chart(
            document.getElementById(
                "turbidityChart"
            ),
            {

                type: "line",

                data: {

                    labels,

                    datasets: [{

                        label: "Turbidity",

                        data: turbidities,

                        borderWidth: 2,

                        fill: false,

                        tension: 0.25
                    }]
                },

                options:
                    getChartOptions(
                        "Turbidity (NTU*)"
                    )
            }
        );


    /* -----------------------------------------
       TDS Chart
       ----------------------------------------- */

    tdsChart =
        new Chart(
            document.getElementById(
                "tdsChart"
            ),
            {

                type: "line",

                data: {

                    labels,

                    datasets: [{

                        label: "TDS",

                        data: tdsValues,

                        borderWidth: 2,

                        fill: false,

                        tension: 0.25
                    }]
                },

                options:
                    getChartOptions(
                        "TDS (ppm*)"
                    )
            }
        );


    /* -----------------------------------------
       Water Quality Score Chart
       ----------------------------------------- */

    scoreChart =
        new Chart(
            document.getElementById(
                "scoreChart"
            ),
            {

                type: "line",

                data: {

                    labels,

                    datasets: [{

                        label: "Water Quality Score",

                        data: scores,

                        borderWidth: 2,

                        fill: false,

                        tension: 0.25
                    }]
                },

                options: {

                    ...getChartOptions(
                        "Score"
                    ),

                    scales: {

                        x: {

                            title: {
                                display: true,
                                text: "Reading"
                            },

                            grid: {
                                display: false
                            }
                        },

                        y: {

                            title: {
                                display: true,
                                text: "HSS / Quality Score"
                            },

                            min: 0,

                            max: 100
                        }
                    }
                }
            }
        );


    historyStatusElement.textContent =
        `${records.length} historical readings`;
}


/* =========================================================
   20. LOAD FIREBASE HISTORY
   ========================================================= */

async function loadHistory() {

    try {

        console.log(`[Dashboard Fetch] GET ${HISTORY_URL}`);
        historyStatusElement.textContent =
            "Loading history...";


        const response =
            await fetch(HISTORY_URL);


        if (!response.ok) {

            throw new Error(
                `API returned HTTP ${response.status}`
            );
        }


        const history =
            await response.json();

        if (!history || (typeof history === "object" && Object.keys(history).length === 0)) {
            historyStatusElement.textContent = "No historical readings available in Firebase.";
            console.warn("[Dashboard History] Received empty history payload from backend.");
            return;
        }


        const records =
            prepareHistoryData(history);


        createHistoryCharts(
            records
        );


        console.log(
            `[Dashboard History] Rendered ${records.length} historical records:`,
            records
        );

    }
    catch (error) {

        console.error(
            "[Dashboard History Error]",
            error
        );

        let msg = "Unable to load historical data.";
        if (error.name === "TypeError" || (error.message && (error.message.includes("fetch") || error.message.includes("Network")))) {
            msg = "Backend unavailable (cannot load history).";
        } else if (error.message && error.message.includes("502")) {
            msg = "Firebase history unavailable (HTTP 502).";
        }

        historyStatusElement.textContent = msg;
    }
}


/* =========================================================
   21. INTERVENTION SIMULATOR
   ========================================================= */

const simTemperatureSlider = document.getElementById("simTemperature");
const simTdsSlider = document.getElementById("simTds");
const simTurbiditySlider = document.getElementById("simTurbidity");
const simTemperatureValue = document.getElementById("simTemperatureValue");
const simTdsValue = document.getElementById("simTdsValue");
const simTurbidityValue = document.getElementById("simTurbidityValue");
const simRunButton = document.getElementById("simRunButton");

const simLiveScoreEl = document.getElementById("simLiveScore");
const simLiveCategoryEl = document.getElementById("simLiveCategory");
const simSimulatedScoreEl = document.getElementById("simSimulatedScore");
const simSimulatedCategoryEl = document.getElementById("simSimulatedCategory");
const simPredictionsEl = document.getElementById("simPredictions");
const simProblemsEl = document.getElementById("simProblems");


// Update slider value displays
if (simTemperatureSlider) {
    simTemperatureSlider.addEventListener("input", () => {
        simTemperatureValue.textContent = parseFloat(simTemperatureSlider.value).toFixed(1);
    });
}

if (simTdsSlider) {
    simTdsSlider.addEventListener("input", () => {
        simTdsValue.textContent = simTdsSlider.value;
    });
}

if (simTurbiditySlider) {
    simTurbiditySlider.addEventListener("input", () => {
        simTurbidityValue.textContent = simTurbiditySlider.value;
    });
}


function updateSimulatorLiveValues(data) {
    if (!data) return;

    const assessment = data.assessment || {};

    if (assessment.hss !== null && assessment.hss !== undefined) {
        simLiveScoreEl.textContent = assessment.hss + "%";
        simLiveCategoryEl.textContent = assessment.category || "--";
        simLiveScoreEl.className = "sim-score-value " + getCategoryClass(assessment.category);
    }

    // Set sliders to current live values
    const sensorData = data.sensor_data || {};
    if (sensorData.temperature !== null && sensorData.temperature !== undefined) {
        simTemperatureSlider.value = sensorData.temperature;
        simTemperatureValue.textContent = parseFloat(sensorData.temperature).toFixed(1);
    }
    if (sensorData.tds !== null && sensorData.tds !== undefined) {
        simTdsSlider.value = Math.min(1000, sensorData.tds);
        simTdsValue.textContent = Math.round(sensorData.tds);
    }
    if (sensorData.turbidity !== null && sensorData.turbidity !== undefined) {
        simTurbiditySlider.value = Math.min(200, sensorData.turbidity);
        simTurbidityValue.textContent = Math.round(sensorData.turbidity);
    }
}


function getCategoryClass(category) {
    if (!category) return "";
    switch (category.toLowerCase()) {
        case "excellent": return "cat-excellent";
        case "good": return "cat-good";
        case "moderate": return "cat-moderate";
        case "poor": return "cat-poor";
        default: return "";
    }
}


if (simRunButton) {
    simRunButton.addEventListener("click", async () => {

        simRunButton.disabled = true;
        simRunButton.textContent = "Simulating...";
        simSimulatedScoreEl.textContent = "...";
        simSimulatedCategoryEl.textContent = "";
        simPredictionsEl.textContent = "";
        simProblemsEl.innerHTML = "";

        try {
            console.log(`[Dashboard Fetch] POST ${SIMULATE_URL}`);
            const response = await fetch(SIMULATE_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    temperature: parseFloat(simTemperatureSlider.value),
                    tds: parseFloat(simTdsSlider.value),
                    turbidity: parseFloat(simTurbiditySlider.value),
                }),
            });

            const result = await response.json();

            if (result.success) {

                const simAssess = result.assessment || {};

                simSimulatedScoreEl.textContent = (simAssess.hss !== null ? simAssess.hss + "%" : "--");
                simSimulatedCategoryEl.textContent = simAssess.category || "--";
                simSimulatedScoreEl.className = "sim-score-value " + getCategoryClass(simAssess.category);

                // Show predictions
                let predText = "";
                if (result.predictions) {
                    if (result.predictions.ph !== null) {
                        predText += `Predicted pH: ${result.predictions.ph.toFixed(2)}`;
                    }
                    if (result.predictions.do !== null) {
                        predText += `  |  Predicted DO: ${result.predictions.do.toFixed(2)} mg/L`;
                    }
                }
                simPredictionsEl.textContent = predText || "Predictions unavailable";

                // Show problems
                if (simAssess.problems && simAssess.problems.length > 0) {
                    simProblemsEl.innerHTML = "<strong style='font-size:12px;color:var(--text-secondary);'>Simulated issues:</strong><ul style='margin-top:6px;list-style:none;padding:0;'>" +
                        simAssess.problems.map(p => `<li style="padding:6px 10px;margin-bottom:4px;font-size:12px;border-left:3px dashed var(--moderate);background:#fffaf0;border-radius:4px;">⚠ ${p}</li>`).join("") +
                        "</ul>";
                } else {
                    simProblemsEl.innerHTML = "<span style='font-size:12px;color:var(--good);'>✓ All simulated parameters are within acceptable ranges.</span>";
                }

            } else {
                simSimulatedScoreEl.textContent = "Error";
                simSimulatedCategoryEl.textContent = result.error || "Simulation failed";
            }

        } catch (err) {
            console.error("[Dashboard Simulation Error]", err);
            simSimulatedScoreEl.textContent = "Error";
            simSimulatedCategoryEl.textContent = (err.name === "TypeError" || err.message.includes("fetch"))
                ? "Backend unavailable"
                : err.message;
        }

        simRunButton.disabled = false;
        simRunButton.textContent = "Run Simulation";
    });
}

const simResetButton = document.getElementById("simResetButton");
if (simResetButton) {
    simResetButton.addEventListener("click", () => {
        if (lastKnownData) {
            updateSimulatorLiveValues(lastKnownData);
        }
        simSimulatedScoreEl.textContent = "--";
        simSimulatedCategoryEl.textContent = "--";
        simSimulatedScoreEl.className = "sim-score-value";
        simPredictionsEl.textContent = "";
        simProblemsEl.innerHTML = "";
    });
}


/* =========================================================
   22. INITIAL LOAD
   ========================================================= */

loadLatestData();

loadHistory();


/* =========================================================
   23. REFRESH
   ========================================================= */

/*
   Latest reading:
   Every 5 seconds.

   History:
   Every 30 seconds.

   We don't need to download the entire history
   every 5 seconds.
*/

setInterval(
    loadLatestData,
    5000
);


setInterval(
    loadHistory,
    30000
);