# AI_Aquatic_Habitat_Assessment

# AI-Based Aquatic Habitat Assessment System

## About the Project
This project is designed to monitor water quality and assess aquatic habitat conditions using IoT and Machine Learning.

An ESP32 collects water parameters using sensors and sends the readings to Firebase. A Flask backend processes the data, predicts pH and Dissolved Oxygen (DO), and calculates a Habitat Suitability Score (HSS). The results are displayed on a web dashboard.

## Technologies Used
- **Hardware:** ESP32, DS18B20, TDS Sensor, Turbidity Sensor
- **Backend:** Python, Flask
- **Machine Learning:** Scikit-learn, Gradient Boosting
- **Database:** Firebase Realtime Database
- **Frontend:** HTML, CSS, JavaScript, Chart.js
- **Testing:** Selenium
- **Project Management:** Jira, GitHub

## Main Features
- Real-time water parameter monitoring
- ML-based pH and DO prediction
- Habitat Suitability Score calculation
- Water quality problem detection and recommendations
- Historical data visualization
- What-if simulation

## Project Structure
```text
AI_Aquatic_Habitat_Assessment/
│
├── backend/
├── frontend/
├── ml/
├── requirements.txt
└── README.md
```

## How to Run

1. Clone the repository:
   ```bash
   git clone <repository-url>
   ```

2. Open the project folder and activate the virtual environment:
   ```bash
   .venv\Scripts\activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Start the Flask backend:
   ```bash
   python backend/app.py
   ```

5. Open another terminal and start the frontend:
   ```bash
   cd frontend
   python -m http.server 5500
   ```

6. Open the dashboard:
   `http://127.0.0.1:5500/index.html`

## Note
pH and DO values are predicted using Machine Learning models. TDS and turbidity readings are sensor-derived values, and calibration is still required for accurate real-world measurements.
