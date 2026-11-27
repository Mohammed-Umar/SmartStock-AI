# SmartStock AI: An Intelligent Household Consumption and Waste Prevention System

> **College CSE Mini Project (5th Semester)**  
> **Domain:** Artificial Intelligence, Applied Machine Learning, Full-Stack Web Development  
> **Tech Stack:** Python, FastAPI, SQLite, Scikit-learn, Pandas, NumPy, HTML5, CSS3, JavaScript (ES6+), Chart.js  

---

## 📌 1. Project Overview & Abstract

In contemporary urban households, grocery mismanagement leads to two major inefficiencies:
1. **Unintended Stockouts:** Running out of critical daily staples (milk, eggs, pantry staples) unexpectedly.
2. **Food Waste & Overstocking:** Purchasing duplicate items while existing inventory expires unseen in pantries or refrigerators, causing unnecessary economic loss and environmental food waste.

**SmartStock AI** is an intelligent household inventory, consumption forecasting, and waste prevention web application. It transitions domestic pantry management from reactive manual tracking to **proactive, machine-learning-driven replenishment**.

### Core Value Propositions:
- **Predictive Refills:** Automatically forecasts exact depletion dates for household items using **Scikit-learn Ridge Regression** with day-of-week seasonality and exponential decay smoothing.
- **Explainable AI (XAI):** Every refill estimate is accompanied by a transparent breakdown showing baseline consumption rates, weekend vs. weekday multipliers, recent trend shifts, and model confidence scores.
- **Anomaly & Waste Alerts:** Employs **Scikit-learn Isolation Forest** alongside statistical IQR/Z-score outlier detection to immediately catch accidental spillages, abnormal usage spikes, or perishable items nearing expiration.
- **Smart Shopping List with Duplicate Prevention:** Auto-generates recommended purchase orders tailored to optimal stock limits, strictly guarding against accidental double-buying.
- **Closed-Loop Restocking Lifecycle:** Marking a shopping list item as purchased automatically updates inventory quantities in the database and logs expense records.
- **Budget & Waste Analytics:** Interactive **Chart.js** data visualizations displaying category spending, monthly expenditure trends, and calculated dollar/unit savings achieved by waste prevention.

---

## 🏗️ 2. System Architecture & Tech Stack

```
                                  +---------------------------------------+
                                  |      Responsive Web Dashboard         |
                                  |   (HTML5, CSS3, ES6 JS, Chart.js)     |
                                  +-------------------+-------------------+
                                                      |
                                             REST API (JSON)
                                                      |
                                  +-------------------v-------------------+
                                  |         FastAPI REST Backend          |
                                  +-------------------+-------------------+
                                                      |
                      +-------------------------------+-------------------------------+
                      |                                                               |
        +-------------v-------------+                                   +-------------v-------------+
        |   Scikit-Learn ML Engine  |                                   |     SQLite Database       |
        |  - Ridge Regression       |                                   |  - Items (Inventory)      |
        |  - Weighted EMA Fallback  |                                   |  - Consumption Logs       |
        |  - Isolation Forest       |                                   |  - Purchase History       |
        |  - XAI Breakdown Generator|                                   |  - Smart Shopping List    |
        +---------------------------+                                   |  - Detected Anomalies     |
                                                                        +---------------------------+
```

### Technology Breakdown:
- **Backend Framework:** [FastAPI](https://fastapi.tiangolo.com/) (High-performance async Python web framework with auto-generated OpenAPI / Swagger documentation).
- **Database:** [SQLite3](https://www.sqlite.org/) (Lightweight zero-config relational database with foreign key cascades and indexed queries).
- **Machine Learning & Analytics:**
  - [Scikit-learn](https://scikit-learn.org/) (`Ridge` regression for time-decay burn-rate estimation, `IsolationForest` for unsupervised anomaly detection).
  - [Pandas](https://pandas.pydata.org/) & [NumPy](https://numpy.org/) (Data wrangling, date-range grouping, exponential weighting).
- **Frontend Architecture:**
  - Semantic HTML5 & Modern CSS3 (Variables, CSS Grid, Glassmorphism aesthetics, responsive cards).
  - Vanilla JavaScript ES6+ (Async/Await API handlers, modal controllers, debounced search filters).
  - [Chart.js](https://www.chartjs.org/) (Interactive doughnut and bar charts for stock health, category spending, and monthly budgets).

---

## 🧠 3. Machine Learning Algorithms & Fallback Hierarchy

### A. Consumption Burn-Rate & Depletion Forecasting
For any inventory item $i$, historical daily consumption logs $C_d$ are aggregated.

1. **High-History Data Points ($\ge 7$ distinct consumption days):**
   - **Feature Vector:** $x = [t, \text{is\_weekend}, \text{day\_of\_week}, \text{rolling\_3d\_avg}]$
   - **Algorithm:** **Ridge Regression** with $L_2$ regularization:
     $$\min_w \|Xw - y\|_2^2 + \alpha \|w\|_2^2$$
   - The model accounts for weekend consumption spikes (e.g. eggs, milk, and coffee consume 20–40% faster on Saturdays and Sundays).
   - **Refill Date Calculation:**
     $$\text{Days Remaining} = \frac{\text{Current Quantity}}{\max(\hat{C}_{\text{daily}}, 0.01)}$$
     $$\text{Predicted Refill Date} = \text{Current Date} + \lceil\text{Days Remaining}\rceil$$

2. **Medium-History Data Points ($3 \le N < 7$ days):**
   - **Algorithm:** **Weighted Exponential Moving Average (EMA, $\alpha=0.35$):**
     $$\bar{C}_{\text{EMA}} = \sum_{j=0}^{N-1} (1-\alpha)^j C_{N-1-j} \Big/ \sum_{j=0}^{N-1} (1-\alpha)^j$$
   - Heavily weights recent usage over older events.

3. **Low-History / Cold Start ($N < 3$ days):**
   - **Algorithm:** Category heuristic based on optimal restocking target divided by standard 14-day turnover cycle:
     $$C_{\text{default}} = \max\left(\frac{\text{Optimal Quantity}}{14}, 0.05\right)$$

### B. Unsupervised Anomaly Detection
Detects consumption spikes (unusual bulk usage or leaks/spillage) and food waste:
- **Isolation Forest ($\ge 8$ logs):** Constructs an ensemble of isolation trees to identify points that have abnormally short path lengths in feature space $[q, \frac{q - \mu}{\sigma}, \text{dow}]$.
- **Statistical Fallback ($< 8$ logs):** Interquartile Range (IQR) and modified Z-score detection:
  $$\text{Upper Threshold} = \text{Median} + \max(1.8 \times \text{IQR}, 0.5 \times \text{Median})$$
- **Waste & Perishable Stagnation:** Any log with `is_waste = 1` or perishable item nearing expiry with stock $> 0$ triggers high-priority alerts.

---

## 📁 4. Project Directory Structure

```
Mini-Project-5th-Sem/
├── app/
│   ├── __init__.py
│   ├── database.py              # SQLite connection pool, schema definitions, and indexes
│   ├── models.py                # Pydantic validation schemas (Request/Response models)
│   ├── ml_engine.py             # Scikit-learn Ridge, EMA fallback, Isolation Forest, XAI logic
│   ├── seed_data.py             # Realistic household staple dataset (30 days of consumption)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── items.py             # Inventory CRUD and stock status endpoints
│   │   ├── consumption.py       # Consumption logging & quick-consume endpoints
│   │   ├── predictions.py       # Refill forecasting & explainability endpoints
│   │   ├── anomalies.py         # Anomaly scan, list, and resolution endpoints
│   │   ├── shopping.py          # Smart shopping list & duplicate-prevention endpoints
│   │   └── analytics.py         # Dashboard metrics, Chart.js datasets, and demo reset
│   └── static/
│       ├── index.html           # Full single-page dashboard application
│       ├── css/
│       │   └── style.css        # Sleek, responsive dark-slate design system
│       └── js/
│           └── app.js           # Frontend controller, API integration, and Chart.js setup
├── main.py                      # FastAPI entrypoint and static route mounting
├── requirements.txt             # Python package dependencies
├── test_app.py                  # Automated test suite validating end-to-end workflows
└── README.md                    # Project documentation & viva guide
```

---

## 🚀 5. Local Setup & Execution Guide

### Prerequisites
- Python 3.9+ (Python 3.9, 3.10, 3.11, or 3.12)
- Modern web browser (Chrome, Safari, Edge, or Firefox)

### Step 1: Clone or Navigate to the Project Directory
```bash
cd /path/to/Mini-Project-5th-Sem
```

### Step 2: Create and Activate a Python Virtual Environment
On macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```
On Windows:
```cmd
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Required Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Run Automated Verification Tests
```bash
python test_app.py
```
*You will see all verification tests pass, validating database seeding, ML forecasting, duplicate buying prevention, and purchase restocking.*

### Step 5: Start the Application Server
```bash
python main.py
```
*Alternatively, run via Uvicorn directly:*
```bash
uvicorn main.py:app --host 127.0.0.1 --port 8000 --reload
```

### Step 6: Access the Application
Open your web browser and navigate to:
- **Web Application Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger API Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Alternative Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🖥️ 6. Core Features & Usage Walkthrough

### 1. Dashboard Overview
- 4 Stat Cards: Total Monitored Items, Low-Stock / Critical Alerts, Predicted Refills in the next 5 days, and Monthly Spending.
- **Stock Health Chart:** Dynamic doughnut visualization displaying current urgency breakdown.
- **Category Spending Chart:** Bar chart comparing expenses across dairy, pantry, produce, cleaning, and beverages.
- **Quick Consumption Bar:** 1-click consumption logging for fast household pantry updates.

### 2. Inventory Management
- Filter by category, status (Critical, Low Stock, Expiring Soon, Good), or real-time search.
- Color-coded progress bars displaying current stock percentage relative to optimal stock targets.
- Direct quick-consume, edit, and delete actions with confirmation dialogs.

### 3. AI Refill Predictions & Explainability
- Each card presents:
  - Exact days remaining until depletion.
  - Estimated depletion date.
  - Daily burn rate in units/day.
  - Transparent reasons generated by the ML model (historical baseline comparison, weekend seasonality multiplier, confidence score).
  - One-click **"Add Refill to Shopping List"** button.

### 4. Anomaly & Waste Alerts
- Pinpoints unusual events such as sudden spikes (e.g. 140g coffee brew for a brunch event or 0.40 L kitchen olive oil spillage).
- Imminent expiry alerts for perishable goods (e.g., fresh bread expiring within 48 hours).
- Provides options to **Acknowledge** or **Dismiss** alerts.

### 5. Smart Shopping List (Duplicate Prevention Guard)
- Click **"Auto-Generate AI Recommendations"** to automatically populate replenishments for items in critical/low stock.
- **Duplicate Prevention Guard:** If an item is already on the shopping list, duplicate additions are blocked.
- **One-Click Restock:** Clicking **"✓ Restock"** marks the item purchased, immediately increments the inventory stock in the database, and adds a record to purchase history.

### 6. Reset Demo Data
- For evaluator demonstrations or college viva presentations, click **"Reset Demo Data"** in the top header at any time to restore the complete sample household dataset with 30 days of realistic logs.

---

## 🎓 7. College CSE Mini Project Viva Q&A Guide

### Q1: Why did you choose Ridge Regression over Ordinary Least Squares (OLS)?
> **Answer:** Household consumption data often exhibits multicollinearity between rolling moving averages, day-of-week indicators, and time trends. Standard OLS can overfit when variance fluctuates. Ridge regression adds an $L_2$ penalty parameter ($\alpha=1.0$), shrinking coefficients and preventing extreme or negative burn rate predictions, ensuring stable and robust forecasts.

### Q2: How does the system handle "Cold Start" when a user adds a brand-new item?
> **Answer:** The application implements a tiered fallback hierarchy:
> 1. $\ge 7$ consumption days: Scikit-learn Ridge regression with seasonality.
> 2. $3$ to $6$ consumption days: Weighted Exponential Moving Average (EMA, $\alpha=0.35$).
> 3. $< 3$ consumption days: Rule-based category turnover heuristic (target quantity / 14 days).
> As the user logs daily usage, the system seamlessly transitions to ML predictions.

### Q3: How does the system prevent duplicate buying and overstocking?
> **Answer:** The recommendation engine inspects both `current_quantity` and whether an unpurchased record already exists in `shopping_list`. If an item is already active on the list, it is skipped. When manual addition is attempted, a database constraint check blocks duplicates. Furthermore, the restock quantity is bounded by `optimal_quantity - current_quantity` to prevent overstocking perishables.

### Q4: How is Anomaly Detection implemented?
> **Answer:** We employ **Scikit-learn Isolation Forest** (`contamination=0.10`) on feature tuples $[q, \text{relative\_deviation}, \text{dow}]$. Since Isolation Forest isolates outliers by randomly partitioning feature values, abnormal events require fewer splits and receive negative anomaly scores. For small sample sizes, we utilize an IQR/Z-score statistical fallback.

---

## 📄 8. License & Academic Attribution
Developed as an academic Mini Project for Bachelor of Engineering / B.Tech in Computer Science and Engineering (CSE). Code is open-source for educational and demonstration purposes.
